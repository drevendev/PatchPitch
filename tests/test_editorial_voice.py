"""Actual pinned compiler integration, with public designed demonstration preferences."""
import copy
from pathlib import Path

import pytest

pytest.importorskip("quillgrain.consumer")

from patchpitch import editorial as e, editorial_generation as writing
from patchpitch.run_store import read_json, write_json, RunError
from patchpitch.voice import prepare_voice
from patchpitch.jobs import VoiceConfig
from test_editorial import workspace, planned, patch, model

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("language", ["en", "ru"])
def test_editorial_compiler_snapshot_and_channel_scope(workspace, language):
    planned(workspace)
    config = {"mode": "local_pack", "path": "voice", "register": "maker_announcement"}
    # Use a separate workspace in each language, keeping original immutable inputs untouched.
    source = workspace.parent / "editorial.json"
    value = read_json(source)
    value["language"] = language
    value["voice"] = {**config, "path": str(ROOT / "examples/editorial/voice")}
    value.pop("style")
    write_json(source, value)
    root = workspace.parent / ("voice-" + language)
    e.initialize(source, root)
    root, manifest, doc, inputs = e.load(root)
    request = writing.voice_request(root, doc, inputs)
    assert request.voice_bundle["context"]["language"] == language
    assert request.voice_bundle["context"]["tags"] == ["social.longform"]
    assert request.style == "voice"
    payload, identity = writing.prompt_payload(root, doc, inputs, "outline")
    assert "SELECTED AUTHOR VOICE" in payload["messages"][0]["content"]
    assert "Use a personal, direct explanation" in payload["messages"][0]["content"]
    assert identity["build_id"] == doc.voice_id or identity["build_id"] == request.voice_bundle["context"]["build_id"]
    before = doc.revision_id
    rendering = __import__("patchpitch.editorial_render", fromlist=["export"])
    preview = workspace.parent / ("preview-" + language)
    rendering.export(root, preview)
    assert "Use a personal, direct explanation" not in (preview / "preview.html").read_text(encoding="utf-8")
    assert e.load(root)[2].revision_id == before


def test_explicit_voice_switch_changes_future_requests_only(workspace, model):
    planned(workspace)
    before = e.load(workspace)[2]
    patch(workspace, [{"type": "voice", "base": str(ROOT / "examples/editorial"),
                       "config": {"mode": "local_pack", "path": "voice", "register": "maker_announcement"}}])
    doc = e.load(workspace)[2]
    assert doc.voice_id is not None and doc.sections == before.sections
    result = writing.propose(workspace, "section", "voiced-section", "S01")
    attempt = read_json(workspace / "attempts/voiced-section.json")
    assert attempt["voice"]["build_id"] and "editorial.concrete" in attempt["payload"]["messages"][0]["content"]
    assert e.load(workspace)[2].sections == before.sections


def test_wrong_channel_bundle_is_rejected_before_inference(workspace, model):
    value = prepare_voice(VoiceConfig(mode="local_pack", path="voice"), ROOT / "examples/editorial", language="en", format="x_single")
    bundle_path = workspace.parent / "wrong-channel.json"
    write_json(bundle_path, value)
    before = e.load(workspace)[2].revision_id
    with pytest.raises(RunError):
        patch(workspace, [{"type": "voice", "base": str(workspace.parent), "config": {"mode": "bundle", "path": "wrong-channel.json"}}])
    assert not model and e.load(workspace)[2].revision_id == before
