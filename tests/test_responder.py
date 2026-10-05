import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("incident_responder", Path(__file__).resolve().parents[1] / "incident-response" / "server.py")
responder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(responder)


def test_synthetic_requires_exact_labels():
    assert responder.classify({"labels": {"alertname": "ResponderTest", "test": "true"}}) == "synthetic"
    with pytest.raises(ValueError):
        responder.classify({"labels": {"alertname": "ResponderTest"}})
    with pytest.raises(ValueError):
        responder.classify({"labels": {"alertname": "UnrelatedAlert"}})


def test_duplicate_and_resolved_never_launch_extra_agent(tmp_path, monkeypatch):
    tasks = []
    class Queue:
        def submit(self, work):
            tasks.append(work)
    monkeypatch.setattr(responder, "EVIDENCE", tmp_path)
    monkeypatch.setattr(responder, "POOL", Queue())
    monkeypatch.setattr(responder, "ACTIVE", {})
    alert = {"status": "firing", "labels": {"alertname": "ResponderTest", "test": "true"}}
    first = responder.receive({"alerts": [alert]})["incidents"][0]
    second = responder.receive({"alerts": [alert]})["incidents"][0]
    assert first["incident_id"] == second["incident_id"]
    assert second["status"] == "duplicate"
    assert len(tasks) == 1
    alert["status"] = "resolved"
    assert responder.receive({"alerts": [alert]})["incidents"][0]["status"] == "resolved"
    assert len(tasks) == 1
    assert not responder.ACTIVE


def test_evidence_limits_and_trace_correlation(monkeypatch):
    calls = []
    trace = "ab" * 16
    def fake_fetch(backend, path, params=None):
        calls.append((backend, path, params))
        return {"trace_id": trace} if backend == "loki" else {}
    monkeypatch.setattr(responder, "fetch", fake_fetch)
    monkeypatch.setattr(responder, "git", lambda *args: "abc123\n")
    packet = responder.collect({"labels": {}}, "real")
    assert packet["affected_route"] == "/api/orders/{order_id}"
    assert packet["window"]["end_unix"] - packet["window"]["start_unix"] == 600
    assert calls[1][2]["limit"] == 100
    assert packet["trace_ids"] == [trace]
    assert calls[2][:2] == ("tempo", "/api/traces/" + trace)


def test_synthetic_has_no_telemetry_collection_or_fix_instruction(monkeypatch):
    monkeypatch.setattr(responder, "fetch", lambda *args: pytest.fail("synthetic queried telemetry"))
    monkeypatch.setattr(responder, "git", lambda *args: "abc123\n")
    packet = responder.collect({"labels": {"test": "true"}}, "synthetic")
    prompt = responder.prompt_for(packet)
    assert "Do not modify any product file" in prompt
    assert "no answer or final-line phrase is prescribed" in prompt


def test_malformed_and_unauthorized_alerts_fail_before_scheduling():
    for payload in ({}, {"alerts": []}, {"alerts": [None]}, {"alerts": [{"status": "firing", "labels": []}]}):
        with pytest.raises(ValueError):
            responder.receive(payload)
