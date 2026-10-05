# Order Tracker

AI Dev Tools Zoomcamp Homework 4: a FastAPI/SQLite order tracker with OpenTelemetry metrics, structured logs and traces, Collector, Prometheus, Loki, Tempo, Grafana, and a local headless incident responder.

## Start and verify

Use Docker Desktop with Compose, Python 3.11+, `uv`, and an already-installed/authenticated Codex CLI for the responder. Run from this repository:

```bash
ORDER_TRACKER_VERSION=$(git rev-parse HEAD) docker compose up --build -d --wait
uv run --frozen pytest -q
curl -i http://localhost:8000/healthz
```

- App: <http://localhost:8000>
- Grafana dashboard: <http://localhost:3000/d/order-tracker>
- Grafana alert rules: <http://localhost:3000/alerting/list>
- Prometheus: <http://localhost:9090>

Grafana uses anonymous Admin access for this local homework. Published ports bind to loopback; this configuration is not for a public server. Set `ORDER_TRACKER_PORT=18080` on the startup command if port 8000 is occupied. Data persists in named Docker volumes. Tempo readiness can lag container startup; verify `curl -f http://localhost:3200/ready` before querying it.

Order lookups emit `order_lookup_requests_total` in Prometheus, labeled by `http_route` and `http_response_status_code`. Logs and traces share trace IDs, also returned in the `X-Trace-Id` response header for handled responses. Console telemetry is visible with `docker compose logs app`. The dashboard links metrics, Loki logs and Tempo traces. The 5xx rule evaluates every 10 seconds over a 2-minute window, with no pending delay and explicit Normal handling of absent data.

## Local incident responder

The responder runs on the host, separately from Compose, to use the installed Codex CLI. Validate its restricted permissions first, then keep it running in a terminal:

```bash
uv sync --frozen
codex --version
.venv/bin/python incident-response/probe_sandbox.py
RESPONDER_DEPLOYED_VERSION=$(git rev-parse HEAD) .venv/bin/python incident-response/server.py
```

Use the version actually deployed in `RESPONDER_DEPLOYED_VERSION` if it differs from HEAD. The endpoint is <http://localhost:8001/alerts>; health is <http://localhost:8001/healthz>. Grafana inside Docker reaches the host via `http://host.docker.internal:8001/alerts`. Do not change the responder to a public bind address. The permission probe must pass on the current machine before launch; it verifies repository read access, scoped writes, denied unrelated access and denied network access.

Run the required synthetic notification before the real incident:

```bash
curl -X POST http://localhost:8001/alerts \
  -H 'Content-Type: application/json' \
  -d '{"alerts":[{"status":"firing","labels":{"alertname":"ResponderTest","test":"true"},"annotations":{"summary":"Test notification; no incident to fix"}}]}'
```

The response includes an incident ID. Poll `http://localhost:8001/incidents/INCIDENT_ID` until completed or failed. Exact commands, bounded evidence, agent output, file hashes and changes are retained in `incident-response/evidence/INCIDENT_ID/`. Synthetic investigations have read-only repository access; real investigations can write only `app/` and `tests/`. See [responder policy](incident-response/POLICY.md).

## Incident exercise

After configuring the Grafana webhook contact point to the responder, request the seeded express order:

```bash
curl -i http://localhost:8000/api/orders/express-1002
```

Repeat only as needed across metrics export/scrape cycles to register a counter increase. Wait for Grafana Firing, the actual webhook, and the headless agent's completed investigation. Review its recorded changes and tests before rebuilding:

```bash
uv run --frozen pytest -q
ORDER_TRACKER_VERSION=$(git rev-parse HEAD) docker compose up --build -d --wait
curl -i http://localhost:8000/api/orders/express-1002
curl -i http://localhost:8000/healthz
```

Verify matching recovery telemetry and Grafana returning to Normal after the 2-minute window. Once the incident is fixed, reproducing the original failure requires an explicit checkout of the recorded pre-fix checkpoint in a separate clone; do not overwrite the completed homework checkout. This procedure does not assume a root cause before the agent investigates.

## Evidence and shutdown

Baseline and phased evidence is under `evidence/`. Observed answers so far: Q1 `{"status":"ok"}`, Q2 200, Q3 404 for the requested `standard-1002`, Q4 Normal. The existing synthetic agent's complete response and exact final line are in [response.txt](incident-response/evidence/20261005T154439Z-bfb36253/response.txt). These are historical observations, not values inserted into the application.

Stop the responder with Ctrl-C in its terminal, then stop the stack without deleting data:

```bash
docker compose down
```

Do not add `-v` unless you intentionally want to delete the order and telemetry data.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Web page |
| GET | `/healthz` | Database health check |
| GET | `/api/orders` | List orders |
| POST | `/api/orders` | Create an order |
| GET | `/api/orders/{order_id}` | Check an order |
| PATCH | `/api/orders/{order_id}` | Change an order status |

Three sample orders are created on an empty database. Run one app container at a time with the SQLite volume.
