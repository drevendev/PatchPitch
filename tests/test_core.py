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
        return {"done": True, "model": "MOCK", "message": {"content": json.dumps(copy.deepcopy(draft_data))}}
    monkeypatch.setattr(generator, "ollama_json", transport)
    result = generator.generate(PitchInput.model_validate(input_data))
    assert len(sent) == 1
    serialized = json.dumps(sent[0])
    assert "Cloud sync" not in serialized and "C04" not in serialized
    assert sent[0]["stream"] is False and isinstance(sent[0]["format"], dict)
    assert len(sent[0]["messages"]) == 1
    assert sent[0]["messages"][0]["role"] == "user"
    assert "UNTRUSTED SOURCE DATA" in sent[0]["messages"][0]["content"]
    model_schema=sent[0]["messages"][0]["content"].split("OUTPUT JSON SCHEMA (structure only; author the prose yourself):\n",1)[1].split("\n\nUNTRUSTED SOURCE DATA",1)[0]
    assert json.loads(model_schema) == sent[0]["format"]
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
    draft_data["intro"]["text"] = "Now 90% faster. Visit https://invented.example."
    draft = Draft.model_validate(draft_data)
    warnings = validate_draft(draft, PitchInput.model_validate(input_data))
    assert len(warnings) == 2
    assert markdown(draft, "Read the guide.").endswith("Read the guide.\n")


def test_spelled_number_drift_is_flagged(input_data, draft_data):
    input_data["changes"][0]["text"] = "Queue three jobs at level 10."
    draft_data["intro"]["text"] = "Queue nine items at level 10."
    warnings = validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data))
    assert any("“9”" in warning for warning in warnings)


def test_omitted_main_feature_limits_are_flagged(input_data, draft_data):
    input_data["changes"][0]["text"] = "Plan up to 3 jobs at level 10, expanding to 5 at level 50."
    draft_data["highlights"][0]["text"] = "Plan up to five jobs."
    warnings = validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data))
    assert any("Highlight 1: source numbers not mentioned: 10, 3, 50" in warning for warning in warnings)


def test_complete_named_list_need_not_repeat_count(input_data,draft_data):
    input_data["changes"][0]["text"]="Three new goods: flax, beeswax, slate. Buy up to 20 units."
    draft_data["highlights"][0]["text"]="New goods include flax, beeswax and slate; buy up to 20 units."
    request=PitchInput.model_validate(input_data)
    assert not any("source numbers not mentioned" in w for w in validate_draft(Draft.model_validate(draft_data),request))
    draft_data["highlights"][0]["text"]="New goods include flax and slate; buy up to 20 units."
    assert any("source numbers not mentioned: 3" in w for w in validate_draft(Draft.model_validate(draft_data),request))


def test_numbers_are_checked_against_the_actual_cited_fact(input_data, draft_data):
    input_data["changes"][1]["text"] = "Export up to 12 notebooks."
    draft_data["highlights"][0] = {"text": "Search up to 12 notes.", "source_ids": ["C01"]}
    warnings = validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data))
    assert any("“12”" in warning and "cited facts" in warning for warning in warnings)


def test_details_are_exported_and_validated(input_data, draft_data):
    draft_data["details"] = [{"text": "Export a notebook as Markdown.", "source_ids": ["C02"]}]
    draft = Draft.model_validate(draft_data)
    validate_draft(draft, PitchInput.model_validate(input_data))
    assert "## Also in this update\n\n- Export a notebook" in markdown(draft)
    draft_data["details"][0]["source_ids"] = ["C04"]
    with pytest.raises(DraftError, match="excluded"):
        validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data))


def test_voice_cannot_supply_factual_support(input_data, draft_data):
    input_data["voice_reference"] = "My old product exports 99 notebooks."
    draft_data["intro"]["text"] = "Export 99 notebooks."
    request = PitchInput.model_validate(input_data)
    assert generator.model_input(request)["voice_reference"] == input_data["voice_reference"]
    assert any("“99”" in warning for warning in validate_draft(Draft.model_validate(draft_data), request))


def test_keep_an_export_is_required_guidance(input_data, draft_data):
    input_data["changes"][0]["text"] = "Before clearing browser data, keep an export from Settings."
    with pytest.raises(DraftError, match="backup"):
        validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data))


def test_paused_recovery_does_not_imply_a_backup_instruction(input_data):
    from patchpitch.validation import required_note_ids
    input_data["changes"][0]["text"]="Keep play paused; the current game export remains available."
    assert required_note_ids(PitchInput.model_validate(input_data)) == []


def test_broad_exception_wording_is_flagged(input_data, draft_data):
    input_data["changes"][0]["text"] = "Basic resources do not prevent recovery."
    draft_data["highlights"][0]["text"] = "Basic resources are unaffected."
    assert any("unaffected" in warning for warning in validate_draft(Draft.model_validate(draft_data), PitchInput.model_validate(input_data)))


def test_full_update_outline_excludes_plans_and_protects_note():
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / "examples/idle-fantasy-shop.json").read_text(encoding="utf-8"))
    request = PitchInput.model_validate(data)
    model_data = generator.model_input(request)
    assert model_data["outline"] == {"highlights": [["C01"], ["C02"], ["C03"]], "details": [["C04"], ["C05"], ["C06"], ["C07"]], "note": ["C08"]}
    assert "C09" not in json.dumps(generator.build_payload(request))
    assert any("requires Workshop level 10" in fact for fact in model_data["selected_changes"][0]["facts"])
    assert model_data["voice_reference"].startswith("Tone brief from in-game item descriptions")
    assert generator.build_payload(request)["format"]["properties"]["details"]["minItems"] == 4


def test_schema_never_supplies_announcement_prose(input_data, draft_data):
    input_data["changes"][0]["text"] = "Queue up to three jobs. Each row asks for 1–99 completions."
    request = PitchInput.model_validate(input_data)
    schema = generator.build_payload(request)["format"]
    def inspect(node):
        if isinstance(node, dict):
            if "text" in node.get("properties", {}):
                assert "const" not in node["properties"]["text"]
                assert "enum" not in node["properties"]["text"]
                assert "maxLength" not in node["properties"]["text"]
            for value in node.values(): inspect(value)
        elif isinstance(node, list):
            for value in node: inspect(value)
    inspect(schema)
    assert "Queue up to three jobs." not in json.dumps(schema)
    draft_data["highlights"][0]["text"] = "Arrange up to three jobs, choosing 1–99 completions for each."
    draft = Draft.model_validate(draft_data)
    generator.validate_contract(draft, schema)
    draft_data["highlights"][0]["retained_facts"] = ["Queue three jobs."]
    with pytest.raises(DraftError, match="retained"):
        generator.validate_contract(Draft.model_validate(draft_data), schema)


def test_generated_words_are_exported_without_rewriting(monkeypatch, input_data, draft_data):
    prose = "Search notes by title; a name is enough."
    draft_data["highlights"][0]["text"] = prose
    raw=copy.deepcopy(draft_data)
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: {"done": True, "message": {"content": json.dumps(raw)}})
    result = generator.generate(PitchInput.model_validate(input_data))
    assert result["raw_draft"] == raw
    assert result["draft"]["highlights"][0]["text"] == raw["highlights"][0]["text"]
    assert result["automated_cleanup"] == []
    assert prose in result["markdown"]


def test_missing_selected_topic_is_rejected(monkeypatch,input_data,draft_data):
    raw=copy.deepcopy(draft_data)
    raw["highlights"].pop()
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:{"done":True,"message":{"content":json.dumps(raw)}})
    with pytest.raises(generator.GenerationError,match="omitted a selected topic"):
        generator.generate(PitchInput.model_validate(input_data))


def test_changed_source_outline_is_rejected(monkeypatch,input_data,draft_data):
    raw=copy.deepcopy(draft_data)
    raw["highlights"][0]["source_ids"]=["C02"]
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:{"done":True,"message":{"content":json.dumps(raw)}})
    with pytest.raises(generator.GenerationError,match="source outline"):
        generator.generate(PitchInput.model_validate(input_data))


def test_technical_fact_context_is_not_appended_to_copy(monkeypatch,input_data,draft_data):
    input_data["changes"][0]["text"]="Technical context: title_only_match=true."
    raw=copy.deepcopy(draft_data)
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:{"done":True,"message":{"content":json.dumps(raw)}})
    result=generator.generate(PitchInput.model_validate(input_data))
    assert "title_only_match" in result["sources"]["C01"]
    assert "title_only_match" not in result["markdown"]


def test_prompt_changes_apply_without_a_server_restart(monkeypatch,tmp_path,input_data):
    prompt_file=tmp_path/"release.txt"
    monkeypatch.setattr(generator,"PROMPT_FILE",prompt_file)
    request=PitchInput.model_validate(input_data)
    prompt_file.write_text("First prompt",encoding="utf-8")
    assert generator.build_payload(request)["messages"][0]["content"].startswith("First prompt")
    prompt_file.write_text("Updated prompt",encoding="utf-8")
    assert generator.build_payload(request)["messages"][0]["content"].startswith("Updated prompt")


def test_patch_example_is_independent_of_devlog():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "examples/idle-fantasy-shop.json").read_text(encoding="utf-8"))
    assert data == json.loads((root / "patchpitch/static/example.json").read_text(encoding="utf-8"))
    provenance = json.loads((root / "examples/idle-fantasy-shop.provenance.json").read_text())
    assert provenance["base"].startswith("e83ddda") and provenance["head"].startswith("c4389af")
    assert provenance["devlog_used_as_input"] is False
    assert provenance["voice_source"]["path"] == "src/locales/en.ts"
    assert data["voice_reference"].startswith("Tone brief from in-game item descriptions")
    payload = json.dumps(generator.build_payload(PitchInput.model_validate(data)))
    assert "devlog/1714671" not in payload
    assert "The workshop can now remember a short plan" not in payload
    assert "let the fields rest" not in payload
    assert all(ref["path"].startswith("src/") for refs in provenance["facts"].values() for ref in refs)


def test_no_advice_or_secondary_topics_without_sources(input_data,draft_data):
    request=PitchInput.model_validate(input_data)
    schema=generator.build_payload(request)["format"]
    assert schema["properties"]["note"] == {"type":"null","const":None}
    assert schema["properties"]["details"] == {"type":"array","const":[]}
    draft_data["note"]={"text":"Back up before updating to 12.3.","source_ids":["C01"]}
    with pytest.raises(DraftError,match="unsupported note"):
        generator.validate_contract(Draft.model_validate(draft_data),schema)


def test_cut_off_headline_is_rejected(input_data,draft_data):
    draft_data["title"]["text"]="Avoid duplicate check-"
    with pytest.raises(DraftError,match="cut off"):
        validate_draft(Draft.model_validate(draft_data),PitchInput.model_validate(input_data))


def test_cut_off_body_is_rejected(input_data,draft_data):
    draft_data["highlights"][0]["text"] = "Workers can supply materials, but the batch-"
    with pytest.raises(DraftError,match="Highlight 1 appears cut off"):
        validate_draft(Draft.model_validate(draft_data),PitchInput.model_validate(input_data))


def test_compound_number_words_do_not_create_false_drifts(input_data,draft_data):
    input_data["changes"][0]["text"] = "Each entry runs 1 to 99 times."
    draft_data["highlights"][0]["text"] = "Run each entry one to ninety-nine times."
    assert not any("Highlight 1" in warning for warning in validate_draft(Draft.model_validate(draft_data),PitchInput.model_validate(input_data)))


def test_pronominal_one_is_not_a_numeric_claim(input_data,draft_data):
    input_data["changes"][0]["text"]="Buy an upgrade before the next tier."
    draft_data["highlights"][0]["text"]="Buy the lower upgrade before the higher one."
    assert not any("“1”" in warning for warning in validate_draft(Draft.model_validate(draft_data),PitchInput.model_validate(input_data)))


def test_explicit_backup_cannot_silently_disappear(input_data,draft_data):
    input_data["changes"][0]["text"]="Export a backup from Settings before moving devices."
    request=PitchInput.model_validate(input_data)
    payload=generator.build_payload(request)
    assert "note" in payload["format"]["required"]
    with pytest.raises(DraftError,match="backup"):
        validate_draft(Draft.model_validate(draft_data),request)
    draft_data["note"]={"text":input_data["changes"][0]["text"],"source_ids":["C01"]}
    validate_draft(Draft.model_validate(draft_data),request)


def test_unreferenced_selected_fact_warns(input_data,draft_data):
    draft_data["title"]["source_ids"]=["C01"]
    draft_data["intro"]["source_ids"]=["C01"]
    draft_data["highlights"]=[block for block in draft_data["highlights"] if "C02" not in block["source_ids"]]
    warnings=validate_draft(Draft.model_validate(draft_data),PitchInput.model_validate(input_data))
    assert any("C02" in warning for warning in warnings)


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
