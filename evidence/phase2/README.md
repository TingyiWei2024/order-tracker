# Phase 2 / Q2

The documented GET `/api/orders/standard-1001` returned **200 OK**. The actual
`order_lookup_requests` console metric records `http.response.status_code: 200`
and `http.route: /api/orders/{order_id}` (console-telemetry.txt lines 92–104).

The HTTP `x-trace-id` is `c7cc0b1df8593e9446124f2f95e9767c`; the emitted log and
span share that trace ID and span ID `98d6d01f80e3f78d`. The metric includes a
matching exemplar. See standard-1001.http and console-telemetry.txt.

Validation: `uv run --frozen pytest -q`: 6 passed, 2 existing dependency warnings.
The telemetry tests cover 200, handled 404, and a synthetic unhandled 500 without
invoking or repairing the express incident. They verify low-cardinality route,
status, signal correlation, and exclusion of credentials and request content.
`docker compose up --build -d --wait` passed (compose-up.txt).

Console export is always active. Setting `OTEL_EXPORTER_OTLP_ENDPOINT` to an
OTLP/HTTP base URL additionally exports all three signals to `/v1/metrics`,
`/v1/logs`, `/v1/traces`. Counter export interval is five seconds.
