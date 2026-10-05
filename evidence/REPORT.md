# Homework 4 observed evidence

Branch: `codex/hw4-complete`. Baseline: `72de4478257813e3ca3a285988f3ad759ec4ea8d`.
Final implementation and recovery evidence are committed locally; obtain the exact final commit with `git rev-parse HEAD`. Independent final QA is performed after that commit and reported separately, without modifying the reviewed checkout.

| Question | Observed answer | Evidence |
| --- | --- | --- |
| Q1 | HTTP **200**, body `{"status":"ok"}` | [baseline response](phase1/healthz.txt), [3 baseline tests](phase1/pytest.txt) |
| Q2 | **200** | [console metric/log/span](phase2/console-telemetry.txt), [HTTP](phase2/standard-1001.http); trace `c7cc0b1df8593e9446124f2f95e9767c` |
| Q3 | **404** | [Prometheus metric](phase3/metric.json), [Grafana metric](phase3/grafana-metric.json), [Grafana log](phase3/grafana-logs.json), [Grafana trace](phase3/grafana-trace.json); trace `8a9b18dd806d4091f17179f352216b92` |
| Q4 | **Normal** | [evaluated state](phase4/evaluated-rules.json) after [required request](phase4/standard-1002.http), [active rule](phase4/rule.json) |
| Q5 | Exact last line below | [full response](../incident-response/evidence/20261005T154439Z-bfb36253/response.txt), [execution state](../incident-response/evidence/20261005T154439Z-bfb36253/state.json) |
| Q6 | Invalid date arithmetic when calculating express delivery across month boundaries | [independent agent diagnosis](../incident-response/evidence/20261005T154950Z-37543c43/response.txt), [exact agent patch](../incident-response/evidence/20261005T154950Z-37543c43/git-after.patch) |

## Q5 exact last line

> No files were read or modified, and no commands or external services were invoked. Treat this as a test notification; further investigation would require evidence of actual failure or impact.

No required phrase was injected. The installed Codex CLI was invoked through the actual synthetic webhook and returned exit code 0; source hashes were unchanged. Both runs explicitly used model `gpt-6-astra`, selected from the existing host configuration; each incident records its exact argv and sandbox configuration.

## Real incident and recovery

Incident `20261005T154950Z-37543c43`: [bounded evidence](../incident-response/evidence/20261005T154950Z-37543c43/evidence.json), [actual webhook](../incident-response/evidence/20261005T154950Z-37543c43/webhook.json), [agent prompt](../incident-response/evidence/20261005T154950Z-37543c43/prompt.txt), [complete execution events](../incident-response/evidence/20261005T154950Z-37543c43/events.jsonl).

`express-1002` returned [500](phase6/express-1002-before.http), Grafana [Fired](phase6/firing-rules.json), and its webhook invoked the responder. The agent inspected code and operational evidence without answer choices or root-cause hints. Five of six new regression cases failed before the one-line application fix. Replacing calendar-field `replace(day=day + 2)` with `timedelta(days=2)` preserves valid date rollover.

After rebuilding, the [same request](phase6/express-1002-after.http) returned **200** with estimated delivery **2026-10-02**. [Recovery metric](phase6/recovery/metric.json), [log](phase6/recovery/logs.json), and [trace](phase6/recovery/trace.json) correlate `b9c4d06f1eb1662aa264df8e07aa8fa6`. [Health](phase6/healthz-after.http) is HTTP200 / `{"status":"ok"}`. [Full suite](phase6/final-tests.txt): **17 passed**, two existing dependency deprecation warnings. [Grafana](phase6/recovery-rules.json) is Normal after recovery checks. The [resolved webhook](../incident-response/evidence/20261005T155150Z-8ff08f43/webhook.json) is preserved; its earlier arrival reflected the rolling window aging out and is not used alone as proof of the fix.

The supplied request omitted Q6 multiple-choice wording. The official public homework link could not be retrieved (404), so no option letter is invented. Select the option describing incorrect express delivery date arithmetic / invalid day at month boundaries; the factual root cause is verified above.

## Operation and scope

See [README](../README.md) for exact full-stack, responder, test, replay and safe-stop commands. App: http://localhost:8000 ; Grafana: http://localhost:3000/d/order-tracker ; responder POST: http://localhost:8001/alerts . All published ports are loopback. Grafana is anonymous Admin for this local exercise. Telemetry data uses local named volumes, with one-day backend retention. No production credentials are supplied.

The responder is a separate host process using existing Codex authentication. Its agent shell tools have no network access, only minimal runtime/repository reads, and only `app/` plus `tests/` writes for real incidents; synthetic mode is read-only. [Six actual sandbox probes](../incident-response/sandbox-probes.json) passed. The agent cannot write Git metadata or push/merge; the orchestrator made local commits and rebuilt the app. Responder deduplication is in-memory, sufficient for the controlled exercise, and resets on service restart.

No host software was installed or host configuration altered. Project dependencies were installed with the existing uv into the project virtual environment. No secrets, credential material, databases or Docker internals were committed. Nothing was pushed, merged, rebased or history-rewritten. [Changed-file manifest](changed-files.txt) lists the submission changes from baseline.
