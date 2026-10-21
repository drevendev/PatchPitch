"""MOCK response retention. No inference, retries, rewriting or disk persistence."""
import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from patchpitch import generator
from patchpitch.app import app


@pytest.mark.parametrize("format", ["devlog", "community", "short", "x_single", "x_thread"])
@pytest.mark.parametrize("failure", ["inline_source", "invalid_json", "incomplete", "unavailable"])
def test_all_formats_retain_failed_response_without_retry(monkeypatch, input_data, draft_data, format, failure):
    body = copy.deepcopy(input_data)
    body.update(format=format, cta_text="")
    social = format.startswith("x_")
    if social:
        body["post_count"] = 3
        draft = {"posts": [{"text": "C01: An unapproved response.", "source_ids": ["C01"]}
                           for _ in range(3 if format == "x_thread" else 1)]}
    elif format == "devlog":
        draft = copy.deepcopy(draft_data)
        draft["intro"]["text"] = "C01: An unapproved response."
    else:
        draft = {"text": "C01: An unapproved response.", "source_ids": ["C01"], "hashtags": []}
    raw = {"done": failure != "incomplete", "model": "ACTUAL_TEST_MODEL",
           "message": {"content": "not JSON" if failure == "invalid_json" else json.dumps(draft)}}
    original = copy.deepcopy(raw)
    calls = []

    def transport(path, payload, timeout):
        calls.append(copy.deepcopy(payload))
        if failure == "unavailable":
            raise generator.GenerationError("ollama_unavailable", "Local model is unavailable.", 503)
        return raw

    monkeypatch.setattr(generator, "ollama_json", transport)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/social" if social else "/api/pitch", json=body)
    assert response.status_code == (503 if failure == "unavailable" else 502)
    data = response.json()
    assert len(calls) == 1 and "draft" not in data
    assert data["evidence"]["raw_response"] == (None if failure == "unavailable" else original)
    assert raw == original
    assert data["evidence"]["returned_model"] == (None if failure == "unavailable" else "ACTUAL_TEST_MODEL")
    assert data["evidence"]["configured_model"] == generator.MODEL
    assert data["evidence"]["elapsed_seconds"] >= 0
    assert data["evidence"]["request_sha256"] == hashlib.sha256(json.dumps(calls[0], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@pytest.mark.parametrize("format,limit", [("community", 1600), ("short", 280)])
def test_overflow_retains_the_whole_response(monkeypatch, input_data, format, limit):
    body = {**input_data, "format": format, "cta_text": ""}
    raw = {"done": True, "model": "MOCK", "message": {"content": json.dumps({
        "text": "a" * limit + ".", "source_ids": ["C01"], "hashtags": []})}}
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: raw)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        result = client.post("/api/pitch", json=body).json()
    assert result["error"]["code"] == "format_overflow"
    assert result["evidence"]["raw_response"] == raw


@pytest.mark.parametrize("format", ["devlog", "community", "short"])
def test_accepted_legacy_response_has_original_and_input_snapshot(monkeypatch, input_data, draft_data, format):
    body = {**input_data, "format": format, "cta_text": ""}
    draft = draft_data if format == "devlog" else {"text": "Find notes by title.", "source_ids": ["C01"], "hashtags": []}
    raw = {"done": True, "model": "MOCK", "message": {"content": json.dumps(draft)}}
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: raw)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/pitch", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["raw_response"] == raw and result["raw_draft"] == draft
    assert result["input_snapshot"]["changes"] == body["changes"]
    assert result["input_snapshot"]["format"] == format
    assert result["automated_cleanup"] == []
