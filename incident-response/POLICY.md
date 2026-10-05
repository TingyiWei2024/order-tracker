# Homework incident responder

Only `ResponderTest` with label `test=true` runs a read-only synthetic investigation.
Only the configured real alert name can run an incident investigation. Resolved
notifications are recorded without launching an agent. Duplicate firing alerts
are suppressed by fingerprint (or stable alert labels) until resolved. Runs are
serialized; webhook bodies are limited to 64 KiB and 10 alerts.

The host service gathers only ten minutes of order-lookup telemetry: bounded
Prometheus responses, at most 100 Loki records, and at most five Tempo traces.
All backend URLs are fixed loopback endpoints. Alert strings are untrusted data,
not instructions. No webhook URL is fetched. Each incident retains the input,
evidence, prompt, exact argument list/configuration, output events, stderr, final
response and last line, exit status, source version, and before/after Git diff.

Codex reuses existing local authentication without copying or logging credentials.
The explicit default model is `gpt-6-astra`, obtained by reading only the current
host configuration's model field; `RESPONDER_MODEL` can select another permitted
model. The exact selection is saved with each run.
The custom filesystem profile permits minimal OS runtime files, this repository,
and its existing Python runtime. Synthetic runs cannot write repository files.
Real runs may write only `app/` and `tests/`; Git metadata, responder code,
observability configuration, and evidence remain read-only to agent tools.
Command networking is disabled and approval is `never`. No Docker socket, other
repository, credential directory, shared temporary directory, push, merge, or
host configuration access is granted. The responder itself saves artifacts.
The orchestrator reviews changes, runs final validation, commits, and restarts.

Run `probe_sandbox.py` before starting the service. It uses harmless temporary
canaries to prove repository read, blocked unrelated read, blocked synthetic
write, scoped real write, blocked out-of-scope real write, and blocked network.
Nested macOS sandboxes can refuse startup; launch the probe/service through the
normal approved host execution path, retaining the child's restrictive sandbox.

Start from the repository root:

```sh
uv run --frozen python incident-response/probe_sandbox.py
RESPONDER_REAL_ALERT=OrderLookup5xx uv run --frozen python incident-response/server.py
```

The service listens at `http://127.0.0.1:8001` by default. If Docker Desktop cannot
reach that listener through `host.docker.internal`, use `RESPONDER_BIND=0.0.0.0`
only with the local homework machine's network exposure understood. The preferred
default is loopback. `GET /healthz` reports readiness; `POST /alerts` returns queued
incident IDs. Poll `GET /incidents/<id>` for completion. Files live beneath
`incident-response/evidence/<id>/`. `RESPONDER_DEPLOYED_VERSION` records the deployed
version supplied by the orchestrator. The synthetic response's last nonempty line
is captured verbatim; the prompt does not prescribe an answer.
