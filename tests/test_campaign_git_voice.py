"""Committed-only extraction and local engine compilation with synthetic text."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from test_campaigns import job_files, transport
from patchpitch import campaigns, generator, voice
from patchpitch.jobs import VoiceConfig
from patchpitch.run_store import RunError, read_json, write_json


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def test_unattended_git_and_no_changes(job_files, transport, monkeypatch, tmp_path):
    job, out, data = job_files
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "Synthetic Test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "notes.py").write_text("local = False\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Initial")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "notes.py").write_text("local = True\n", encoding="utf-8")
    git(repo, "commit", "-am", "Enable local drafts")
    (repo / "notes.py").write_text("uncommitted = 'excluded'\n", encoding="utf-8")
    normal = generator.ollama_json
    def extraction(path, payload, **kwargs):
        if "facts" in payload["format"]["properties"]:
            transport.append(copy.deepcopy(payload))
            assert "uncommitted" not in payload["messages"][0]["content"]
            raw = {"facts": [{"text": "PatchPitch prepares local drafts.", "evidence_ids": ["D01"], "kind": "implemented"}]}
            return {"done": True, "model": "TEST_ONLY", "message": {"content": json.dumps(raw)}}
        return normal(path, payload, **kwargs)
    monkeypatch.setattr(generator, "ollama_json", extraction)
    data["source"] = {"kind": "git_range", "repository": "repo", "base": base, "files": ["notes.py"], "candidate_selection": "all_valid_candidates"}
    data["targets"] = [data["targets"][0]]
    write_json(job, data)
    assert campaigns.run(job, out)[1] == 0
    sources = read_json(out / "sources.json")
    assert sources["review_status"] == "machine_selected_unreviewed"
    assert sources["source_context"]["worktree_dirty"] is True
    assert len(transport) == 2
    pool = read_json(out / "facts/candidates.json")
    selection = {"preview_sha256": pool["preview_sha256"], "candidate_sha256": pool["candidate_sha256"],
                 "candidates_file": "run/facts/candidates.json", "selected_ids": ["B00F00"]}
    write_json(tmp_path / "selection.json", selection)
    data["source"].update(candidate_selection="selection_file", selection_file="selection.json")
    write_json(job, data)
    assert campaigns.run(job, tmp_path / "selected-run")[1] == 0
    assert len(transport) == 3  # Selected snapshot is reused, no second extraction.
    data["source"] = {"kind": "git_range", "repository": "repo", "base": "HEAD", "files": ["notes.py"], "candidate_selection": "all_valid_candidates"}
    write_json(job, data)
    value, code = campaigns.run(job, tmp_path / "unchanged")
    assert code == 0 and value["status"] == "no_changes" and len(transport) == 3


def test_local_pack_custom_register_and_channel(tmp_path):
    pytest.importorskip("quillgrain.consumer")
    pack = {"schema_version": "quillgrain.voice-pack/v1", "id": "synthetic.campaign", "version": "1.0.0",
        "visibility": "private", "status": "REVIEWED", "languages": ["en"], "registers": ["engineering_article"],
        "extends": [], "examples": [], "provenance": [], "limitations": [],
        "compatibility": {"engine": "0.1", "schema": "v1"},
        "permissions": {"local_analysis": True, "retrieval": True, "private_git_excerpt": False,
            "approved_model_hosts": ["ollama"], "public_redistribution": False},
        "rules": [{"id": "synthetic.direct", "kind": "preference", "scope": {"tags": ["social.longform"]},
            "instruction": "Prefer concrete observations.", "priority": 90, "enforcement": "human_review",
            "evidence_ids": [], "origin": "designed_default", "status": "REVIEWED"}]}
    write_json(tmp_path / "voice.json", pack)
    config = VoiceConfig(mode="local_pack", path=".", register="engineering_article")
    bundle = voice.prepare_voice(config, tmp_path, language="en", format="dev_article")
    assert bundle["context"]["register"] == "engineering_article"
    assert bundle["context"]["visibility"] == "private"
    assert voice.validate_bundle(bundle, language="en", format="dev_article", register="engineering_article")
    with pytest.raises(ValueError, match="VOICE_REGISTER_MISMATCH"):
        voice.validate_bundle(bundle, register="maker_announcement")
    with pytest.raises(ValueError, match="VOICE_CHANNEL_MISMATCH"):
        voice.validate_bundle(bundle, format="telegram")
    write_json(tmp_path / "bundle.json", bundle)
    imported = voice.prepare_voice(VoiceConfig(mode="bundle", path="bundle.json", register="engineering_article"),
                                   tmp_path, language="en", format="dev_article")
    assert imported == bundle


def test_missing_voice_blocks_only_dependent_target(job_files, transport):
    job, out, data = job_files
    data["voices"] = {"missing": {"mode": "bundle", "path": "missing.json"}}
    data["targets"][0]["voice"] = "missing"
    write_json(job, data)
    value, code = campaigns.run(job, out)
    assert code != 0 and value["targets"]["telegram"]["status"] == "failed"
    assert value["targets"]["dev"]["status"] == "succeeded"
