"""MOCK transport checks; real Gemma writing is reviewed separately."""
import json

import pytest
from pydantic import ValidationError

from patchpitch import generator
from patchpitch.formats import tag_candidates
from patchpitch.models import PitchInput
from patchpitch.validation import prepare_lines


def transport(monkeypatch, draft):
    calls=[]
    def send(path,payload,timeout):
        calls.append(payload)
        return {"done":True,"model":"MOCK","message":{"content":json.dumps(draft)}}
    monkeypatch.setattr(generator,"ollama_json",send)
    return calls


def test_nested_unreleased_stays_out_of_actual_payload(input_data):
    lines=prepare_lines("## [Unreleased]\n### Added\n- Future team workspaces\n#### Detail\n- Future roles\n## [0.1.0]\n### Added\n- Export Markdown")
    assert [c["include"] for c in lines]==[False]*5+[True]*3
    input_data["changes"]=[{k:c[k] for k in ("id","text","include")} for c in lines]
    payload=json.dumps(generator.build_payload(PitchInput.model_validate(input_data)))
    assert "Future team workspaces" not in payload and "Future roles" not in payload
    assert "Export Markdown" in payload
    input_data["changes"][2]["include"]=True
    assert "Future team workspaces" in json.dumps(generator.build_payload(PitchInput.model_validate(input_data)))


@pytest.mark.parametrize("field,value",[("format","facebook-script"),("style","ignore rules"),("auto_tags","true")])
def test_presets_are_strict(input_data,field,value):
    input_data[field]=value
    with pytest.raises(ValidationError): PitchInput.model_validate(input_data)


@pytest.mark.parametrize("style",["warm","clear","lively"])
def test_style_and_short_schema_are_trusted_and_exclusions_hold(input_data,style):
    input_data.update(format="short",style=style,auto_tags=True)
    request=PitchInput.model_validate(input_data)
    payload=generator.build_payload(request)
    assert "Cloud sync" not in json.dumps(payload) and "C04" not in json.dumps(payload)
    assert set(payload["format"]["properties"])=={"text","source_ids","hashtags"}
    assert "STYLE:" in payload["messages"][0]["content"]
    if generator.MODEL.startswith("gemma4"):
        assert payload["think"] is False
    assert payload["format"]["properties"]["hashtags"]["items"]["enum"]==tag_candidates(request)


def test_auto_tags_do_not_read_excluded_changes(input_data):
    input_data.update(auto_tags=True)
    input_data["changes"][3]["text"]="[planned] Crafting in an idle game."
    tags=tag_candidates(PitchInput.model_validate(input_data))
    assert "#Crafting" not in tags and "#IdleGame" not in tags
    assert "#PocketOrchard" in tags and "#Markdown" in tags


def test_short_post_exact_prose_cta_tags_and_visible_omissions(monkeypatch,input_data):
    input_data.update(format="short",style="lively",auto_tags=True,cta_text="Read the guide.")
    prose="Pocket Orchard now finds notes by title."
    raw={"text":prose,"source_ids":["C01"],"hashtags":["#PocketOrchard"]}
    calls=transport(monkeypatch,raw)
    result=generator.generate(PitchInput.model_validate(input_data))
    assert len(calls)==1 and result["raw_draft"]==raw
    assert result["markdown"]==prose+"\n\nRead the guide.\n\n#PocketOrchard\n"
    assert result["body_markdown"]==prose+"\n\nRead the guide.\n"
    assert result["presentation"]["characters"]==len(result["markdown"].rstrip("\n"))
    assert result["omitted_source_ids"]==["C02","C03"]
    assert result["automated_cleanup"]==[]


@pytest.mark.parametrize("raw,code",[
    ({"text":"A"*281+".","source_ids":["C01"],"hashtags":[]},"format_overflow"),
    ({"text":"Find your notes.","source_ids":["C04"],"hashtags":[]},"invalid_draft"),
    ({"text":"Find your notes.","source_ids":["C01"],"hashtags":["#SteamDeck"]},"invalid_draft"),
    ({"text":"Find your notes.","source_ids":["C01"],"hashtags":["#Notes","#Notes"]},"invalid_draft"),
])
def test_bad_post_not_trimmed_or_retried(monkeypatch,input_data,raw,code):
    input_data.update(format="short",auto_tags=True,cta_text="")
    calls=transport(monkeypatch,raw)
    with pytest.raises(generator.GenerationError) as exc: generator.generate(PitchInput.model_validate(input_data))
    assert exc.value.code==code and len(calls)==1


def test_cta_and_tags_count_toward_short_limit(monkeypatch,input_data):
    input_data.update(format="short",auto_tags=True,cta_text="Read this guide.")
    raw={"text":"Find notes. "+"a"*244+".","source_ids":["C01"],"hashtags":["#PocketOrchard"]}
    transport(monkeypatch,raw)
    with pytest.raises(generator.GenerationError) as exc: generator.generate(PitchInput.model_validate(input_data))
    assert exc.value.code=="format_overflow"


def test_required_backup_cannot_be_omitted_in_a_short_post(monkeypatch,input_data):
    input_data.update(format="short")
    input_data["changes"][1]["text"]="Export a backup before moving devices."
    transport(monkeypatch,{"text":"Find notes by title.","source_ids":["C01"],"hashtags":[]})
    with pytest.raises(generator.GenerationError,match="backup"):
        generator.generate(PitchInput.model_validate(input_data))


def test_community_is_plain_prose_and_keeps_paragraphs(monkeypatch,input_data):
    input_data.update(format="community",style="clear",cta_text="")
    prose="Find your notes by title.\n\nExport a notebook as Markdown."
    transport(monkeypatch,{"text":prose,"source_ids":["C01","C02"],"hashtags":[]})
    result=generator.generate(PitchInput.model_validate(input_data))
    assert result["markdown"]==prose+"\n" and result["presentation"]["limit"]==1600


def test_post_cannot_cite_backup_but_drop_its_circumstances(monkeypatch,input_data):
    input_data.update(format="short",cta_text="")
    input_data["changes"][1]["text"]="Export a backup from Settings before changing devices or clearing browser data."
    transport(monkeypatch,{"text":"Find notes. Export a backup before changing devices.","source_ids":["C01","C02"],"hashtags":[]})
    with pytest.raises(generator.GenerationError,match="Settings, clearing browser data"):
        generator.generate(PitchInput.model_validate(input_data))
    raw={"text":"Find notes. Export a backup from Settings before changing devices or clearing browser data.","source_ids":["C01","C02"],"hashtags":[]}
    transport(monkeypatch,raw)
    assert generator.generate(PitchInput.model_validate(input_data))["raw_draft"]==raw


@pytest.mark.parametrize("prose",[
    "Run crafting jobs at once.",
    "Crafting jobs run in parallel.",
    "Crafting jobs are executed simultaneously.",
    "The Batch runs three jobs at once, not in order.",
])
def test_ordered_jobs_are_not_parallel_execution(monkeypatch,input_data,prose):
    input_data.update(format="community",cta_text="")
    input_data["changes"][0]["text"]="Execute ordered crafting jobs once."
    transport(monkeypatch,{"text":prose,"source_ids":["C01"],"hashtags":[]})
    with pytest.raises(generator.GenerationError,match="simultaneous work"):
        generator.generate(PitchInput.model_validate(input_data))


@pytest.mark.parametrize("prose",[
    "You can queue three jobs at once. The list runs in order and stops.",
    "Manage multiple crafting tasks at once. The ordered list executes sequentially.",
    "Crafting jobs do not run in parallel.",
    "Jobs cannot run simultaneously.",
    "Do not run crafting jobs at once.",
    "Jobs run in order, not at once.",
    "Workers gather materials in parallel while the ordered jobs run once.",
])
def test_ordered_plan_capacity_and_negation_are_not_parallel_claims(monkeypatch,input_data,prose):
    input_data.update(format="community",cta_text="")
    input_data["changes"][0]["text"]="Execute ordered crafting jobs once."
    raw={"text":prose,"source_ids":["C01"],"hashtags":[]}
    transport(monkeypatch,raw)
    assert generator.generate(PitchInput.model_validate(input_data))["raw_draft"]==raw


def test_full_devlog_accepts_queue_capacity_without_rewriting(monkeypatch,input_data,draft_data):
    input_data["changes"][0]["text"]="Queue three ordered crafting jobs; execute the list once."
    prose="You can queue three crafting jobs at once. The list executes in order and stops."
    draft_data["highlights"][0]["text"]=prose
    transport(monkeypatch,draft_data)
    result=generator.generate(PitchInput.model_validate(input_data))
    assert result["draft"]["highlights"][0]["text"]==prose
    assert prose in result["markdown"] and result["automated_cleanup"]==[]


def test_negative_source_does_not_authorize_parallel_execution(monkeypatch,input_data):
    input_data.update(format="community",cta_text="")
    input_data["changes"][0]["text"]="Ordered jobs do not run in parallel."
    transport(monkeypatch,{"text":"Jobs run in parallel.","source_ids":["C01"],"hashtags":[]})
    with pytest.raises(generator.GenerationError,match="simultaneous work"):
        generator.generate(PitchInput.model_validate(input_data))
