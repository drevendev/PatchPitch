import copy
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from patchpitch import generator, sessions
from patchpitch.app import app
from patchpitch.fact_packs import load_pack, prepare_pack
from patchpitch.models import PitchInput


def response(monkeypatch, input_data, draft_data):
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: {
        "done": True, "model": "MOCK", "message": {"content": json.dumps(draft_data)}})
    return generator.generate(PitchInput.model_validate(input_data))


def session_for(data):
    original = copy.deepcopy(data)
    data = copy.deepcopy(data)
    data["local_record_id"] = "A01"
    req = data["input_snapshot"]
    return {"kind": "patchpitch_session", "schema_version": 1,
        "form": {"product": req["product"]["name"], "description": req["product"]["description"],
            "audience": req["audience"], "release": req["release_label"], "voice": req["voice_reference"],
            "cta": req["cta_text"], "changes": "\n".join(c["text"] for c in req["changes"]),
            "media_note": "", "format": req["format"], "style": req["style"], "intent": "show_result",
            "post_count": 5, "auto_tags": False, "writing_goal": "release"},
        "changes": req["changes"], "preview_text": "\n".join(c["text"] for c in req["changes"]),
        "pack_context": None,
        "drafts": [{"data": data, "markdown": "# Мои правки\n\n<literal> & e\u0301\n\n", "tags": [],
            "edited": True, "editing": True, "posts": []}],
        "active_key": json.dumps([req["product"]["name"], req["release_label"], req["format"]], separators=(",", ":")),
        "records": [{"schema_version": 1, "id": "A01", "recorded_at": data["context"]["generated_at"],
            "status": "accepted", "client_elapsed_seconds": 1.0, "input_snapshot": req,
            "response": original, "error": None, "evidence": None}], "record_choice": "A01"}


def test_all_formats_keep_source_provenance(monkeypatch, input_data, draft_data):
    input_data.update(source_references=[{"api_id": c["id"], "stable_id": "F"+c["id"][1:],
        "source_url": "https://example.org/commit/123", "source_ref": "commit 123"} for c in input_data["changes"]],
        pack_id="reviewed", pack_version="v1", pack_sha256="a"*64, context_overrides=["audience"])
    for fmt in ("devlog", "community", "short"):
        input_data["format"] = fmt
        draft = draft_data if fmt == "devlog" else {"text": "Pocket Orchard finds notes by title.", "source_ids": ["C01"], "hashtags": []}
        data = response(monkeypatch, input_data, draft)
        assert data["source_snapshot"][0]["source_url"] == "https://example.org/commit/123"
        assert data["context"]["pack_sha256"] == "a"*64
        assert data["context"]["context_overrides"] == ["audience"]
        assert "https://example.org/commit/123" not in json.dumps(generator.build_payload(PitchInput.model_validate(input_data)))


def test_guidance_only_outline_is_valid_and_extra_blocks_rejected(monkeypatch, input_data, draft_data):
    text = "Export a backup from Settings before changing devices or clearing browser data."
    input_data["changes"] = [{"id": "C01", "text": text, "include": True}]
    block = {"text": "Keep your data available.", "source_ids": ["C01"], "retained_facts": []}
    draft = {"title": {**block, "text": "Keep your data"}, "intro": block, "highlights": [],
        "details": [], "note": {**block, "text": text}, "hashtags": []}
    assert response(monkeypatch, input_data, draft)["draft"]["highlights"] == []
    draft["highlights"] = [{**block, "retained_facts": ["Unexpected retained prose."]}]
    with pytest.raises(generator.GenerationError):
        response(monkeypatch, input_data, draft)


def test_session_validation_preserves_exact_text_and_never_calls_model(monkeypatch, input_data, draft_data):
    saved = session_for(response(monkeypatch, input_data, draft_data))
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: pytest.fail("Opening must not call model"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        actual = client.post("/api/session/validate", json=saved)
    assert actual.status_code == 200
    assert actual.json() == saved


@pytest.mark.parametrize("damage", ["version", "url", "source", "active", "record", "posts", "timing", "map"])
def test_bad_session_is_rejected(monkeypatch, input_data, draft_data, damage):
    saved = session_for(response(monkeypatch, input_data, draft_data))
    data = saved["drafts"][0]["data"]
    if damage == "version": saved["schema_version"] = 99
    if damage == "url": data["source_snapshot"][0]["source_url"] = "javascript:alert(1)"
    if damage == "source": data["sources"]["C01"] = "Changed original"
    if damage == "active": saved["active_key"] = "missing"
    if damage == "record": saved["records"] = []
    if damage == "posts": saved["drafts"][0]["posts"] = [{"id": "P01", "text": "Wrong format", "source_ids": ["C01"]}]
    if damage == "timing": data["meta"]["elapsed_seconds"] = "invalid"
    if damage == "map": data["source_map"][0]["source_ids"] = ["C03"]
    with pytest.raises((ValueError, ValidationError)):
        sessions.validate_file(saved)


def test_profile_contains_no_release_or_drafts():
    profile = {"kind": "patchpitch_profile", "schema_version": 1, "product": {"name": "App", "description": "Local app"},
        "audience": "Makers", "cta_text": "https://example.org"}
    assert sessions.validate_file(profile) == profile
    with pytest.raises(ValueError): sessions.validate_file({**profile, "changes": []})


def test_rejected_input_record_can_be_saved_without_becoming_a_draft(monkeypatch, input_data, draft_data):
    saved = session_for(response(monkeypatch, input_data, draft_data))
    failed = copy.deepcopy(saved["records"][0])
    failed.update(id="A02", status="failed", response=None,
        error={"code": "request_failed", "message": "Input was rejected", "http_status": 422})
    failed["input_snapshot"]["product"]["name"] = "   "
    failed["input_snapshot"]["changes"][0]["include"] = False
    saved["records"].append(failed)
    saved["record_choice"] = "A02"
    assert sessions.validate_file(saved) == saved
    # Relaxing failed input validation must not permit malformed renderer fields.
    failed["input_snapshot"]["product"] = "invalid"
    with pytest.raises(ValueError): sessions.validate_file(saved)
