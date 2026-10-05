import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from opentelemetry.trace import StatusCode

from app.telemetry import OrderLookupTelemetry, ROUTE, Telemetry


@pytest.mark.parametrize("outcome,expected", [("ok", 200), ("missing", 404), ("failure", 500)])
def test_lookup_telemetry_records_actual_status_and_correlates(outcome, expected):
    metrics = InMemoryMetricReader()
    spans = InMemorySpanExporter()
    logs = InMemoryLogRecordExporter()
    telemetry = Telemetry(
        metric_readers=[metrics], span_processors=[SimpleSpanProcessor(spans)],
        log_processors=[SimpleLogRecordProcessor(logs)],
    )
    app = FastAPI()
    app.add_middleware(OrderLookupTelemetry, telemetry=telemetry)

    @app.get(ROUTE)
    def lookup(order_id: str):
        if outcome == "missing":
            raise HTTPException(404, "Order not found")
        if outcome == "failure":
            raise ValueError("private request content")
        return {"id": order_id}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/orders/private-customer-id", headers={"Authorization": "secret"})
        assert response.status_code == expected
        assert client.get("/unrelated").status_code == 404
    points = metrics.get_metrics_data().resource_metrics[0].scope_metrics[0].metrics[0].data.data_points
    assert len(points) == 1
    attrs = {"http.route": ROUTE, "http.request.method": "GET", "http.response.status_code": expected}
    if expected == 500:
        attrs["error.type"] = "ValueError"
    assert points[0].value == 1
    assert points[0].attributes == attrs
    assert len(spans.get_finished_spans()) == 1
    span = spans.get_finished_spans()[0]
    log = logs.get_finished_logs()[0].log_record
    assert log.attributes == attrs
    assert log.trace_id == span.context.trace_id
    assert log.span_id == span.context.span_id
    assert span.attributes["http.response.status_code"] == expected
    assert span.status.status_code == (StatusCode.ERROR if expected == 500 else StatusCode.UNSET)
    if expected != 500:
        assert response.headers["x-trace-id"] == format(span.context.trace_id, "032x")
    if expected == 500:
        assert span.attributes["error.type"] == "ValueError"
    exported = str(span.to_json()) + str(log.attributes) + str(log.body) + str(points)
    for private_value in ("private-customer-id", "secret", "private request content"):
        assert private_value not in exported
    telemetry.meter_provider.shutdown()
    telemetry.tracer_provider.shutdown()
    telemetry.logger_provider.shutdown()
