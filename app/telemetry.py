"""Bounded order-lookup telemetry; console output plus optional OTLP/HTTP."""
import os
import re
import sys
from time import time_ns

from opentelemetry._logs import SeverityNumber
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor, ConsoleLogRecordExporter, SimpleLogRecordProcessor,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode

ROUTE = "/api/orders/{order_id}"


class Telemetry:
    def __init__(self, *, metric_readers=None, span_processors=None, log_processors=None):
        resource = Resource.create({"service.name": "order-tracker"})
        readers = metric_readers if metric_readers is not None else [
            PeriodicExportingMetricReader(ConsoleMetricExporter(out=sys.__stdout__), export_interval_millis=5000)
        ]
        spans = span_processors if span_processors is not None else [
            SimpleSpanProcessor(ConsoleSpanExporter(out=sys.__stdout__))
        ]
        logs = log_processors if log_processors is not None else [
            SimpleLogRecordProcessor(ConsoleLogRecordExporter(out=sys.__stdout__))
        ]
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint and metric_readers is None:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
            base = endpoint.rstrip("/")
            readers.append(PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{base}/v1/metrics"), export_interval_millis=5000
            ))
            spans.append(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{base}/v1/traces")))
            logs.append(BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{base}/v1/logs")))
        self.meter_provider = MeterProvider(resource=resource, metric_readers=readers)
        self.tracer_provider = TracerProvider(resource=resource)
        self.logger_provider = LoggerProvider(resource=resource)
        for processor in spans:
            self.tracer_provider.add_span_processor(processor)
        for processor in logs:
            self.logger_provider.add_log_record_processor(processor)
        self.counter = self.meter_provider.get_meter("order-tracker").create_counter(
            "order_lookup_requests", unit="{request}", description="Completed order lookup requests"
        )
        self.tracer = self.tracer_provider.get_tracer("order-tracker")
        self.logger = self.logger_provider.get_logger("order-tracker")


class OrderLookupTelemetry:
    def __init__(self, app, telemetry=None):
        self.app = app
        self.telemetry = telemetry or Telemetry()

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope["method"] != "GET"
                or not re.fullmatch(r"/api/orders/[^/]+", scope["path"])):
            return await self.app(scope, receive, send)
        attributes = {"http.route": ROUTE, "http.request.method": "GET"}
        status_code = 500

        async def capture_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-trace-id", format(span.get_span_context().trace_id, "032x").encode())
                ]
            await send(message)

        # Disable automatic exception text/stack export: they may contain user input.
        with self.telemetry.tracer.start_as_current_span(
            f"GET {ROUTE}", kind=SpanKind.SERVER, attributes=attributes,
            record_exception=False, set_status_on_exception=False,
        ) as span:
            try:
                await self.app(scope, receive, capture_status)
            except Exception as exc:
                span.set_attribute("error.type", type(exc).__name__)
                attributes["error.type"] = type(exc).__name__
                raise
            finally:
                attributes["http.response.status_code"] = status_code
                span.set_attributes(attributes)
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR))
                self.telemetry.counter.add(1, attributes)
                self.telemetry.logger.emit(
                    timestamp=time_ns(),
                    severity_number=SeverityNumber.ERROR if status_code >= 500 else SeverityNumber.INFO,
                    severity_text="ERROR" if status_code >= 500 else "INFO",
                    body="Order lookup completed", attributes=attributes,
                )
