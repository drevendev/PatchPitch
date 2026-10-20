"""Offline contracts; none of these mocked responses establish Gemma quality."""
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from patchpitch import generator, social
from patchpitch.app import app
from patchpitch.fact_packs import FactPack, load_pack, prepare_pack
from patchpitch.models import SocialInput
from patchpitch.social_count import estimate


@pytest.fixture
def social_input():
    pack = prepare_pack(load_pack("patchpitch"))
    pack["changes"] = [{k: c[k] for k in ("id", "text", "include")} for c in pack["changes"]]
    return {k: v for k, v in pack.items() if k not in {"review_required"}} | {"confirmed": True, "format": "x_thread", "post_count": 5}


def raw_posts(n=5):
    return {"posts": [{"text": f"PatchPitch helps authors inspect selected source notes. Example {i}.", "source_ids": ["C03"]} for i in range(n)]}


def mock_transport(monkeypatch, draft, **identity):
    calls = []
    def send(path, payload, timeout):
        calls.append(payload)
        return {"done": True, "message": {"content": json.dumps(draft)}, **identity}
    monkeypatch.setattr(generator, "ollama_json", send)
    return calls


def test_pack_mapping_review_defaults_and_validation(social_input):
    pack = prepare_pack(load_pack("idle-fantasy-shop"))
    assert [c["id"] for c in pack["changes"]] == [f"C{i:02}" for i in range(1,10)]
    assert [c["id"] for c in pack["changes"] if c["include"]] == ["C01", "C08"]
    assert pack["source_references"][0]["stable_id"] == "F01" and pack["review_required"]
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/api/fact-packs/patchpitch").status_code == 200
    assert client.get("/api/fact-packs/not-a-file").status_code == 404
    data = load_pack("patchpitch").model_dump()
    assert client.post("/api/fact-packs/prepare", json=data).json()["pack_sha256"] == social_input["pack_sha256"]


@pytest.mark.parametrize("mutation", ["version", "duplicate", "oversize", "count", "url", "missing_source"])
def test_invalid_packs_do_not_load(mutation):
    data = load_pack("patchpitch").model_dump()
    if mutation == "version": data["schema_version"] = 2
    if mutation == "duplicate": data["facts"][1]["id"] = data["facts"][0]["id"]
    if mutation == "oversize": data["facts"][0]["text"] = "x" * 6000
    if mutation == "count": data["facts"] *= 2
    if mutation == "url": data["facts"][0]["source_url"] = "javascript:alert(1)"
    if mutation == "missing_source": data["facts"][0].update(source_ref="", source_url="")
    with pytest.raises(ValidationError): FactPack.model_validate(data)


def test_actual_payload_excludes_notes_and_cta_but_keeps_voice_separate(social_input):
    request = SocialInput.model_validate(social_input)
    payload = social.build_payload(request)
    text = json.dumps(payload)
    assert "Automatic Git import" not in text and "C09" not in text
    assert request.cta_text not in text
    assert "source_url" not in text and "source_ref" not in text
    assert "voice_reference" in text and payload["format"]["properties"]["posts"]["minItems"] == 5


@pytest.mark.parametrize("mutation", ["unconfirmed", "empty", "bad_mapping", "bad_stable", "extra", "count", "regenerate"])
def test_invalid_requests_never_call_model(monkeypatch, social_input, mutation):
    calls = mock_transport(monkeypatch, raw_posts())
    if mutation == "unconfirmed": social_input["confirmed"] = False
    if mutation == "empty":
        for c in social_input["changes"]: c["include"] = False
    if mutation == "bad_mapping": social_input["source_references"][0]["api_id"] = "C05"
    if mutation == "bad_stable": social_input["source_references"][0]["stable_id"] = social_input["source_references"][1]["stable_id"]
    if mutation == "extra": social_input["publish"] = True
    if mutation == "count": social_input["post_count"] = 8
    if mutation == "regenerate": social_input["operation"] = "regenerate"
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.post("/api/social", json=social_input).status_code == 422 and calls == []


def test_generated_thread_has_stable_sources_exact_cta_and_raw_response(monkeypatch, social_input):
    raw = raw_posts()
    calls = mock_transport(monkeypatch, raw, model=generator.MODEL, eval_count=21)
    result = social.generate(SocialInput.model_validate(social_input))
    assert len(calls) == 1 and result["raw_draft"] == raw
    assert result["raw_response"]["message"]["content"] == json.dumps(raw)
    assert [p["id"] for p in result["draft"]["posts"]] == [f"P{i:02}" for i in range(1,6)]
    assert result["draft"]["posts"][-1]["text"].endswith("\n\n"+social_input["cta_text"])
    assert social_input["cta_text"] not in result["draft"]["posts"][0]["text"]
    assert result["source_snapshot"][-1]["include"] is False
    assert result["meta"]["returned_model"] == generator.MODEL
    assert "prompt_eval_count" not in result["meta"] and result["meta"]["eval_count"] == 21


@pytest.mark.parametrize("mutation,code", [("count","invalid_draft"),("excluded","invalid_draft"),("duplicate","invalid_draft"),("extra","invalid_draft"),("empty","invalid_draft"),("overflow","format_overflow"),("cutoff","invalid_draft"),("html","invalid_draft")])
def test_malformed_output_is_not_retried_or_rewritten(monkeypatch,social_input,mutation,code):
    raw = raw_posts()
    if mutation == "count": raw["posts"].pop()
    if mutation == "excluded": raw["posts"][0]["source_ids"] = ["C09"]
    if mutation == "duplicate": raw["posts"][0]["source_ids"] = ["C03","C03"]
    if mutation == "extra": raw["posts"][0]["publish_now"] = True
    if mutation == "empty": raw["posts"][0]["text"] = ""
    if mutation == "overflow": raw["posts"][0]["text"] = "x"*281+"."
    if mutation == "cutoff": raw["posts"][0]["text"] = "A truncated draft and"
    if mutation == "html": raw["posts"][0]["text"] = "<script>placeholder</script>."
    calls = mock_transport(monkeypatch, raw)
    with pytest.raises(generator.GenerationError) as exc: social.generate(SocialInput.model_validate(social_input))
    assert exc.value.code == code and len(calls) == 1
    assert exc.value.evidence["raw_response"]["message"]["content"] == json.dumps(raw)


@pytest.mark.parametrize("identity", [{}, {"model":"another:1", "eval_count":True}, {"model":None,"prompt_eval_count":"17"}])
def test_missing_or_mismatched_identity_is_honest(monkeypatch,social_input,identity):
    mock_transport(monkeypatch, raw_posts(), **identity)
    result = social.generate(SocialInput.model_validate(social_input))
    assert result["meta"]["returned_model"] == identity.get("model")
    assert result["meta"]["configured_model"] == generator.MODEL
    assert "eval_count" not in result["meta"] and "prompt_eval_count" not in result["meta"]
    assert any("model" in w.lower() for w in result["warnings"])


def test_regeneration_one_request_uses_snapshot_and_keeps_other_cards(monkeypatch,social_input):
    mock_transport(monkeypatch, raw_posts(),model=generator.MODEL)
    original = social.generate(SocialInput.model_validate(social_input))
    context = [{k:p[k] for k in ("id","text","source_ids")} for p in original["draft"]["posts"]]
    social_input.update(operation="regenerate",target_post_id="P03",thread_context=context,cta_text="")
    draft = {"posts":[{"text":"PatchPitch keeps the original notes available for inspection.","source_ids":["C03"]}]}
    calls = mock_transport(monkeypatch,draft,model=generator.MODEL)
    result = social.generate(SocialInput.model_validate(social_input))
    assert len(calls) == 1 and result["draft"]["posts"][0]["id"] == "P03"
    assert context == [{k:p[k] for k in ("id","text","source_ids")} for p in original["draft"]["posts"]]


def test_backup_circumstances_cannot_disappear_from_thread(monkeypatch,social_input):
    social_input["changes"][0]["text"] = "Export a backup from Settings before changing devices or clearing browser data."
    raw = raw_posts()
    raw["posts"][0] = {"text":"Export a backup from Settings before changing devices.","source_ids":["C01"]}
    mock_transport(monkeypatch,raw)
    with pytest.raises(generator.GenerationError,match="clearing browser data"):
        social.generate(SocialInput.model_validate(social_input))


@pytest.mark.parametrize("text,expected", [("a"*279,279),("a"*280,280),("a"*281,281),("Привет",6),("漢字",4),("e\u0301",1),("😀",2),("Hi http://test.co",26),("http://test.co",23),("👨‍👩‍👧‍👦",11)])
def test_estimate_known_cases(text,expected):
    count = estimate(text)
    assert count["characters"] == expected and count["estimated"]
    assert count["over_limit"] == (expected > 280) and count["requires_x_preview"]


def test_old_generation_missing_identity_is_not_filled(monkeypatch,input_data,draft_data):
    mock_transport(monkeypatch,draft_data)
    from patchpitch.models import PitchInput
    result=generator.generate(PitchInput.model_validate(input_data))
    assert result["meta"]["returned_model"] is None and result["meta"]["model"] is None
    assert "eval_count" not in result["meta"]


@pytest.mark.parametrize("raw",[None,[],"invalid",{"done":"false"},{"done":True,"message":{"content":"invalid JSON"}}])
def test_invalid_envelope_returns_local_failure_evidence(monkeypatch,social_input,raw):
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:raw)
    client=TestClient(app,base_url="http://127.0.0.1")
    result=client.post("/api/social",json=social_input)
    assert result.status_code==502
    if raw is not None:assert result.json()["evidence"]["raw_response"]==raw


def test_cta_that_cannot_fit_is_rejected_before_inference(monkeypatch,social_input):
    calls=mock_transport(monkeypatch,raw_posts())
    social_input["cta_text"]="x"*280
    with pytest.raises(ValidationError,match="call to action"):SocialInput.model_validate(social_input)
    assert calls==[]
