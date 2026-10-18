import copy
import json
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from patchpitch import generator
from patchpitch.app import app
from patchpitch.models import Draft, PitchInput
from patchpitch.validation import DraftError, markdown, prepare_lines, validate_draft


@pytest.fixture
def client():
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield client


def test_excluded_is_absent_from_actual_transport(monkeypatch, input_data, draft_data):
    sent = []
    def transport(path, payload, timeout):
        sent.append(payload)
        return {"done": True, "model": "MOCK", "message": {"content": json.dumps(draft_data)}}
    monkeypatch.setattr(generator, "ollama_json", transport)
    result = generator.generate(PitchInput.model_validate(input_data))
    assert len(sent) == 1
    serialized = json.dumps(sent[0])
    assert "Cloud sync" not in serialized and "C04" not in serialized
    assert sent[0]["stream"] is False and isinstance(sent[0]["format"], dict)
    ids=sent[0]["format"]["$defs"]["Block"]["properties"]["source_ids"]
    assert ids["items"]["enum"] == ["C01","C02","C03"]
    assert ids["maxItems"] == 3 and ids["uniqueItems"] is True
    assert result["sources"]["C01"] == input_data["changes"][0]["text"]


@pytest.mark.parametrize("mutation", ["empty", "long", "all_excluded", "unconfirmed", "id", "extra", "too_many"])
def test_invalid_input_never_calls_model(client, monkeypatch, input_data, mutation):
    def forbidden(*args):
        pytest.fail("Model must not be called")
    monkeypatch.setattr(generator, "generate", forbidden)
    if mutation == "empty": input_data["product"]["name"] = " "
    elif mutation == "long": input_data["changes"][0]["text"] = "a" * 6001
    elif mutation == "all_excluded":
        for c in input_data["changes"]: c["include"] = False
    elif mutation == "unconfirmed": input_data["confirmed"] = False
    elif mutation == "id": input_data["changes"][0]["id"] = "C99"
    elif mutation == "extra": input_data["upstream_url"] = "https://example.com"
    elif mutation == "too_many": input_data["changes"] *= 4
    assert client.post("/api/pitch", json=input_data).status_code == 422


@pytest.mark.parametrize("mutation", ["unknown", "excluded", "duplicate", "empty_ids", "extra", "empty_text", "too_many", "placeholder"])
def test_invalid_output_rejected(input_data, draft_data, mutation):
    if mutation == "unknown": draft_data["title"]["source_ids"] = ["C99"]
    elif mutation == "excluded": draft_data["title"]["source_ids"] = ["C04"]
    elif mutation == "duplicate": draft_data["title"]["source_ids"] = ["C01", "C01"]
    elif mutation == "empty_ids": draft_data["intro"]["source_ids"] = []
    elif mutation == "extra": draft_data["surprise"] = True
    elif mutation == "empty_text": draft_data["title"]["text"] = " "
    elif mutation == "too_many": draft_data["highlights"] *= 2
    elif mutation == "placeholder": draft_data["intro"]["text"] = "TODO write this"
    with pytest.raises((ValidationError, DraftError)):
        validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data))


def test_warnings_and_cta(input_data, draft_data):
    draft_data["intro"]["text"] = "Now 90% faster. Visit https://invented.example"
    draft = Draft.model_validate(draft_data)
    warnings = validate_draft(draft, PitchInput.model_validate(input_data))
    assert len(warnings) == 2
    assert markdown(draft, "Read the guide.").endswith("Read the guide.\n")


def test_spelled_number_drift_is_flagged(input_data, draft_data):
    input_data["changes"][0]["text"] = "Queue three jobs at level 10."
    draft_data["intro"]["text"] = "Queue nine items at level 10."
    warnings = validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data))
    assert any("“9”" in warning for warning in warnings)


def test_markers_and_unreleased():
    changes = prepare_lines("Done.\n[planned] Later\n[internal] Cleanup\n[blocked] Wait\n[unknown] Maybe\n## Unreleased\nFuture\n## Released\nShipped")
    assert [c["include"] for c in changes] == [True, False, False, False, False, False, False, True, True]


@pytest.mark.parametrize("failure,status", [("ollama_unavailable",503),("timeout",504),("model_missing",503),("invalid_json",502)])
def test_errors_are_explicit(client, monkeypatch, input_data, failure, status):
    def fail(request):
        raise generator.GenerationError(failure, "Controlled MOCK fault injection", status)
    monkeypatch.setattr(generator, "generate", fail)
    result = client.post("/api/pitch", json=input_data)
    assert result.status_code == status and result.json()["error"]["code"] == failure


def test_transport_handles_refused_and_timeout(monkeypatch):
    class Failing:
        def __init__(self, exc): self.exc = exc
        def open(self, *args, **kwargs): raise self.exc
    for exception, code in [(urllib.error.URLError(ConnectionRefusedError()), "ollama_unavailable"), (TimeoutError(), "timeout")]:
        monkeypatch.setattr(generator, "OPENER", Failing(exception))
        with pytest.raises(generator.GenerationError) as exc: generator.ollama_json("/api/chat", {})
        assert exc.value.code == code


def test_no_duplicate_concurrent_calls(client, monkeypatch, input_data):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def slow(request):
        calls.append(1); entered.set(); release.wait(5)
        return {"ok": True}
    monkeypatch.setattr(generator, "generate", slow)
    with ThreadPoolExecutor() as pool:
        first = pool.submit(client.post, "/api/pitch", json=input_data)
        assert entered.wait(3)
        second = client.post("/api/pitch", json=input_data)
        release.set()
        assert first.result().status_code == 200
    assert second.status_code == 409 and len(calls) == 1


def test_local_security(client):
    assert client.get("/", headers={"host":"evil.example"}).status_code == 403
    assert client.post("/api/pitch", json={}, headers={"origin":"https://evil.example"}).status_code == 403
    assert client.post("/api/pitch", content="x", headers={"content-type":"text/plain"}).status_code == 415
    assert client.post("/api/pitch", content="x" * 32001, headers={"content-type":"application/json"}).status_code == 413
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]


@pytest.mark.parametrize("raw", [{"done":True,"message":{"content":"oops"}}, {"done":False,"message":{"content":"{}"}}])
def test_bad_live_envelope(monkeypatch, input_data, raw):
    monkeypatch.setattr(generator, "ollama_json", lambda *a,**kw: raw)
    with pytest.raises(generator.GenerationError): generator.generate(PitchInput.model_validate(input_data))
