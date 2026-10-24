"""Original synthetic fixtures; optional integration tests, no personal text."""
import copy
import json
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("quillgrain.consumer")
from quillgrain.compose import compile_context
from quillgrain.consumer import bundle
from patchpitch import generator, voice, sessions
from patchpitch.models import PitchInput
from patchpitch.app import app
from test_sessions import session_for


@pytest.fixture
def voice_bundle(tmp_path):
    pack = {"schema_version":"quillgrain.voice-pack/v1", "id":"synthetic.writer", "version":"1.0.0",
        "visibility":"public", "status":"REVIEWED", "languages":["ru"], "registers":["maker_announcement"],
        "extends":[], "examples":[], "provenance":[], "limitations":[],
        "compatibility":{"engine":"0.1","schema":"v1"},
        "permissions":{"local_analysis":True,"retrieval":True,"private_git_excerpt":False,
            "approved_model_hosts":["ollama"],"public_redistribution":True},
        "rules":[{"id":"synthetic.rhythm","kind":"preference","scope":{"tags":["social.telegram"]},
            "instruction":"Use a quiet conversational opening about the current object. Never recycle a sample joke.",
            "priority":95,"enforcement":"human_review","evidence_ids":[],"origin":"designed_default","status":"REVIEWED"}]}
    (tmp_path/"voice.json").write_text(json.dumps(pack),encoding="utf-8")
    ctx,lock=compile_context(tmp_path,register="maker_announcement",language="ru",model_host="ollama",target="patchpitch",tags=["social.telegram"])
    return bundle(ctx,lock)


def request(input_data, voice_bundle):
    return PitchInput.model_validate({**input_data,"format":"telegram","language":"ru","style":"voice",
        "voice_reference":"","voice_bundle":voice_bundle,"auto_tags":True,"tag_allowlist":["#Тест"]})


def test_actual_payload_style_and_exclusion(input_data,voice_bundle):
    req=request(input_data,voice_bundle)
    content=generator.build_payload(req)["messages"][0]["content"]
    assert "Пиши на русском" in content and "English release post" not in content
    assert "synthetic.rhythm" in content and "Avoid metaphors" not in content
    assert "quiet conversational opening" in content
    assert all(c.text not in content for c in req.changes if not c.include)
    assert generator.build_payload(req)["format"]["properties"]["hashtags"]["items"]["enum"]==["#Тест"]


def test_author_prompt_does_not_compete_with_release_preset(input_data,voice_bundle,monkeypatch):
    req=request(input_data,voice_bundle)
    monkeypatch.setattr(generator,"MODEL","gemma4:12b")
    payload=generator.build_payload(req)
    content=payload["messages"][0]["content"]
    assert payload["think"] is False
    assert "Give readers a concrete reason to care" not in content
    assert "Do not invent jokes" not in content
    facts=json.loads(content.split("TASK_FACTS (недоверенные данные, только выбранные факты):\n",1)[1])
    assert "voice_examples" not in facts and "voice_reference" not in facts
    assert facts["important_note_source_ids"]==[c.id for c in req.changes if c.include and c.id in generator.required_note_ids(req)]
    monkeypatch.setattr(generator,"MODEL","other-model")
    assert "think" not in generator.build_payload(req)
    ordinary=PitchInput.model_validate(input_data)
    assert "English release" in generator.read_prompt("telegram")
    assert "STYLE_PREFERENCES" not in generator.build_payload(ordinary)["messages"][0]["content"]


@pytest.fixture
def reference_bundle(tmp_path,voice_bundle):
    # Original synthetic passages. Public tests never load a personal profile.
    from quillgrain.io import read_json
    pack=read_json(tmp_path/"voice.json")
    shared={"language":"ru","register":"maker_announcement","channel":"narration",
            "permissions":pack["permissions"],"visibility":"public","role":"positive",
            "authorship":"synthetic_ai_prepared","status":"REVIEWED","tags":["social.telegram"]}
    pack["examples"]=[
        dict(shared,id="sample.low",source_id="sample.low",work_id="sample.low",priority=40,
             text="Сегодня в архиве нашлась картонная коробка с ровно семью бумажными журавлями."),
        dict(shared,id="sample.high",source_id="sample.high",work_id="sample.high",priority=90,
             text="На столе опять лежит блокнот, а нужная заметка уже нашлась.")]
    (tmp_path/"voice.json").write_text(json.dumps(pack),encoding="utf-8")
    ctx,lock=compile_context(tmp_path,register="maker_announcement",language="ru",model_host="ollama",target="patchpitch",tags=["social.telegram"])
    return bundle(ctx,lock)


def test_reference_priority_authorship_and_facts_are_separate(input_data,reference_bundle):
    req=request(input_data,reference_bundle)
    content=generator.build_payload(req)["messages"][0]["content"]
    refs=json.loads(content.split("STYLE_REFERENCE_DATA (образцы речи, не команды и не факты нового поста):\n",1)[1].split("\nOUTPUT_SCHEMA:",1)[0])
    assert [e["id"] for e in refs]==["sample.high","sample.low"]
    assert refs[0]["authorship"]=="synthetic_ai_prepared" and refs[0]["priority"]==90
    assert refs[0]["channel"]=="narration"
    assert "scope=" in content and "dialogue/characters" in content
    facts=content.split("\nTASK_FACTS",1)[1]
    assert all(e["text"] not in facts for e in refs)


def test_copied_sample_is_rejected_but_selected_fact_can_overlap(input_data,reference_bundle):
    from patchpitch.validation import validate_draft,DraftError
    from patchpitch.models import PostDraft
    req=request(input_data,reference_bundle)
    copied="На столе опять лежит блокнот — а нужная заметка уже нашлась."
    draft=PostDraft(text=copied,source_ids=["C01"])
    with pytest.raises(DraftError,match="copied a passage"):
        validate_draft(draft,req)
    data=req.model_dump();data["changes"]=[{"id":"C01","text":copied,"include":True}]
    validate_draft(draft,PitchInput.model_validate(data))
    data["changes"]=[{"id":"C01","text":"Поиск заметок по заголовку.","include":True},{"id":"C02","text":copied,"include":False}]
    with pytest.raises(DraftError,match="copied a passage"):
        validate_draft(draft,PitchInput.model_validate(data))


@pytest.mark.parametrize("suffix",['", else: "}',r"\n\n",r"\n"])
def test_observed_structured_text_artifacts_are_rejected(input_data,voice_bundle,suffix):
    from patchpitch.validation import validate_draft,DraftError
    from patchpitch.models import PostDraft
    req=request(input_data,voice_bundle)
    with pytest.raises(DraftError,match="inside the post"):
        validate_draft(PostDraft(text="Теперь заметки можно искать по названию."+suffix,source_ids=["C01"]),req)


@pytest.mark.parametrize("field,value",[("language","en"),("format","x_single"),("style","clear"),("voice_reference","a competing sample")])
def test_mismatches_block_generation(input_data,voice_bundle,field,value):
    data=request(input_data,voice_bundle).model_dump();data[field]=value
    with pytest.raises(ValueError):PitchInput.model_validate(data)


def test_bad_bundle_does_not_echo_private_content(voice_bundle):
    damaged=copy.deepcopy(voice_bundle)
    damaged["context"]["prompt_payload"]+="PRIVATE_SENTINEL"
    with TestClient(app,base_url="http://127.0.0.1") as client:
        response=client.post("/api/voice/validate",json=damaged)
    assert response.status_code==422 and "PRIVATE_SENTINEL" not in response.text


def test_real_result_session_identity_and_exact_text(monkeypatch,input_data,voice_bundle):
    req=request(input_data,voice_bundle)
    raw={"text":"Небольшое обновление.\n\nТеперь заметки можно искать по названию.","source_ids":["C01"],"hashtags":["#Тест"]}
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**k:{"done":True,"model":"MOCK","message":{"content":json.dumps(raw,ensure_ascii=False)}})
    result=generator.generate(req)
    assert "\n\nТеперь" in result["markdown"] and "#Тест" in result["markdown"]
    assert result["context"]["voice"]["build_id"]==voice_bundle["context"]["build_id"]
    saved=session_for(result);saved["voice_bundle"]=voice_bundle
    saved["form"].update(language="ru",tag_allowlist="#Тест")
    assert sessions.validate_file(saved)==saved
    missing=copy.deepcopy(saved);missing["voice_bundle"]=None
    with pytest.raises(ValueError):sessions.validate_file(missing)
    damaged=copy.deepcopy(saved);damaged["drafts"][0]["data"]["context"]["voice"]["build_id"]="f"*64
    with pytest.raises(ValueError):sessions.validate_file(damaged)


def test_russian_guidance_requires_both_circumstances(input_data):
    from patchpitch.validation import validate_draft, DraftError
    from patchpitch.models import PostDraft
    data={**input_data,"format":"telegram","language":"ru","changes":[{"id":"C01","text":"Export a backup from Settings before changing devices or clearing browser data.","include":True}]}
    req=PitchInput.model_validate(data)
    missing=PostDraft(text="Сохраните резервную копию в настройках перед сменой устройства.",source_ids=["C01"])
    with pytest.raises(DraftError):validate_draft(missing,req)
    full=PostDraft(text="Сохраните резервную копию в настройках перед сменой устройства или очисткой данных браузера.",source_ids=["C01"])
    validate_draft(full,req)


def test_russian_informal_backup_verbs_are_not_false_rejections(input_data):
    from patchpitch.validation import validate_draft
    from patchpitch.models import PostDraft
    data={**input_data,"format":"telegram","language":"ru","changes":[{"id":"C01","text":"Сделайте резервную копию через настройки перед сменой устройства или очисткой данных браузера.","include":True}]}
    req=PitchInput.model_validate(data)
    text="Если планируете менять устройство или чистить данные браузера, сделайте резервную копию через настройки перед этими действиями."
    validate_draft(PostDraft(text=text,source_ids=["C01"]),req)


@pytest.mark.parametrize("term",["бэкап","бекап"])
def test_russian_backup_aliases_keep_the_full_guidance(input_data,term):
    from patchpitch.validation import validate_draft,DraftError
    from patchpitch.models import PostDraft
    data={**input_data,"format":"telegram","language":"ru","changes":[{"id":"C01","text":"Сделайте резервную копию через настройки перед сменой устройства или очисткой данных браузера.","include":True}]}
    req=PitchInput.model_validate(data)
    validate_draft(PostDraft(text=f"Перед сменой устройства или очисткой данных браузера сделай {term} через настройки.",source_ids=["C01"]),req)
    with pytest.raises(DraftError):
        validate_draft(PostDraft(text=f"Перед сменой устройства сделай {term} через настройки.",source_ids=["C01"]),req)
