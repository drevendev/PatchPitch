"""Crashes and explicit imports must not turn into duplicate inference or lost edits."""
import copy
import json

import pytest

from patchpitch import editorial as e, editorial_generation as writing, editorial_import as importing
from patchpitch import editorial_x as x, generator
from patchpitch.run_store import RunError, read_json, write_json
from test_editorial import workspace, model, planned, complete, patch


def test_saved_response_recovers_without_another_request(workspace, model, monkeypatch):
    original = writing.write_json
    def crash(path, data):
        if str(path).endswith("saved.json") and data.get("status") == "candidate":
            raise KeyboardInterrupt()
        return original(path, data)
    monkeypatch.setattr(writing, "write_json", crash)
    before = e.load(workspace)[2].revision_id
    with pytest.raises(KeyboardInterrupt):
        writing.propose(workspace, "outline", "saved")
    assert read_json(workspace / "attempts/saved.json")["status"] == "response_saved"
    monkeypatch.setattr(writing, "write_json", original)
    recovered = writing.recover(workspace, "saved")
    assert recovered["status"] == "candidate" and len(model) == 1
    assert e.load(workspace)[2].revision_id == before
    writing.accept(workspace, "saved", before)
    assert e.load(workspace)[2].outline.title == "My local drafts"


def test_inflight_reply_is_stale_after_manual_edit(workspace, model, monkeypatch):
    complete(workspace)
    original = generator.ollama_json
    def concurrent_edit(path, payload, **kwargs):
        section = e.load(workspace)[2].sections[0].model_dump()
        section["blocks"][0]["text"] = "My newer local edit survives."
        patch(workspace, [{"type": "section", "value": section}])
        return original(path, payload, **kwargs)
    monkeypatch.setattr(generator, "ollama_json", concurrent_edit)
    result = writing.propose(workspace, "section", "inflight", "S01")
    assert result["stale"]
    with pytest.raises(RunError) as exc:
        writing.accept(workspace, "inflight", result["revision_id"])
    assert exc.value.code == "REVISION_CONFLICT"
    assert e.load(workspace)[2].sections[0].blocks[0].text == "My newer local edit survives."


def test_manifest_switch_failure_can_retry_without_losing_revision(workspace, monkeypatch):
    before = e.load(workspace)[2].revision_id
    value = {"operation_id": "crash-commit", "expected_revision_id": before,
             "operations": [{"type": "metadata", "value": {"description": "Durable edit"}}]}
    original = e.write_json
    def crash(path, data):
        if str(path).endswith("manifest.json"):
            raise OSError("simulated loss before manifest switch")
        original(path, data)
    monkeypatch.setattr(e, "write_json", crash)
    with pytest.raises(OSError):
        e.apply(workspace, value)
    assert e.load(workspace)[2].revision_id == before
    monkeypatch.setattr(e, "write_json", original)
    after = e.apply(workspace, value)
    assert e.apply(workspace, value) == after
    assert e.load(workspace)[2].metadata.description == "Durable edit"


def test_unknown_and_failed_attempts_never_repeat_silently(workspace, model, monkeypatch):
    def crash(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(generator, "ollama_json", crash)
    with pytest.raises(KeyboardInterrupt):
        writing.propose(workspace, "outline", "unknown")
    with pytest.raises(RunError) as exc:
        writing.recover(workspace, "unknown")
    assert exc.value.code == "INFERENCE_OUTCOME_UNKNOWN"
    with pytest.raises(RunError):
        writing.propose(workspace, "outline", "unknown")
    assert e.status(workspace)["request_count"] == 1 and not model


def test_import_requires_explicit_citations_and_preserves_original(workspace, tmp_path):
    complete(workspace)
    before = e.load(workspace)[2].revision_id
    path = tmp_path / "edited.md"
    path.write_text("## The problem\n\nMy exact imported prose.\n\n## The result\n\nLocal recovery.\n", encoding="utf-8")
    unreviewed = importing.import_markdown(workspace, path, operation_id="unmapped")
    assert unreviewed["status"] == "needs_review"
    assert e.load(workspace)[2].revision_id == before
    with pytest.raises(RunError):
        writing.accept(workspace, "unmapped", before)
    mapped = importing.import_markdown(workspace, path, {"S01": ["C01"], "S02": ["C02"]}, "mapped")
    writing.accept(workspace, mapped["candidate"], mapped["revision_id"])
    assert e.load(workspace)[2].sections[0].blocks[0].text == "My exact imported prose."
    assert not e.load(workspace)[2].article_reviewed
    path.write_text("---\npublished: true\n---\n## The problem\n\nBad import.", encoding="utf-8")
    with pytest.raises(RunError) as exc:
        importing.import_markdown(workspace, path)
    assert exc.value.code == "MARKDOWN_FRONT_MATTER"


def test_private_bundle_reopens_with_history(workspace, tmp_path, model):
    complete(workspace)
    result = writing.propose(workspace, "section", "kept-attempt", "S01")
    writing.reject(workspace, result["candidate"])
    destination = tmp_path / "private-bundle"
    value = importing.bundle(workspace, destination)
    assert value["private"] and e.load(destination)[2] == e.load(workspace)[2]
    assert read_json(destination / "attempts/kept-attempt.json")["raw_response"]["model"] == "MOCK"
    assert read_json(destination / "attempts/kept-attempt.json")["status"] == "rejected"


def test_manual_x_edit_and_stale_reaffirmation_preserve_other_posts(workspace, model):
    complete(workspace)
    first = writing.propose(workspace, "x", "first-series")
    writing.accept(workspace, first["candidate"], first["revision_id"])
    original = read_json(workspace / "attempts/first-series.json")["candidate"]
    changed = x.edit_series(workspace, "P02", "My revised local drafts.", operation_id="manual-x")
    writing.accept(workspace, changed["candidate"], changed["revision_id"])
    current = read_json(workspace / "attempts/manual-x.json")["candidate"]
    assert current[0] == original[0] and current[2] == original[2] and len(model) == 3
    patch(workspace, [{"type": "metadata", "value": {"description": "New reviewed angle"}}])
    patch(workspace, [{"type": "review_article"}])
    reaffirmed = x.edit_series(workspace, reaffirm=True, operation_id="reaffirm-x")
    writing.accept(workspace, reaffirmed["candidate"], reaffirmed["revision_id"])
    assert e.status(workspace)["x_state"] == "awaiting_public_url" and len(model) == 3


def test_batch_explicit_retry_reuses_successful_sections_and_exact_code(workspace, model, monkeypatch):
    planned(workspace)
    original = generator.ollama_json
    failures = []
    def fail_second(path, payload, **kwargs):
        data = json.loads(payload["messages"][0]["content"].split("UNTRUSTED TASK DATA:\n", 1)[1])
        if data["selected_section"]["id"] == "S02" and not failures:
            failures.append(True)
            return {"done": False, "message": {"content": "unfinished"}}
        return original(path, payload, **kwargs)
    monkeypatch.setattr(generator, "ollama_json", fail_second)
    with pytest.raises(RunError):
        writing.draft(workspace, "resume-batch")
    assert len(model) == 1
    with pytest.raises(RunError):
        writing.draft(workspace, "resume-batch")
    assert len(model) == 1
    recovered = writing.draft(workspace, "resume-batch", retry_failed=True)
    assert len(model) == 2 and e.status(workspace)["request_count"] == 3
    writing.accept(workspace, recovered["candidate"], recovered["revision_id"])
    section = e.load(workspace)[2].sections[1]
    assert section.blocks[-1].kind == "code" and section.blocks[-1].snippet_id == "C02-code-1"
    assert read_json(workspace / "attempts/resume-batch-S01.json")["status"] == "accepted"


def test_catalog_refresh_preserves_article_review_and_immutable_inputs(workspace, model):
    complete(workspace)
    before = (workspace / "inputs/snapshot.json").read_bytes()
    current = e.load(workspace)[3]["catalog"]
    current["version"] = "an-explicit-new-observation-selection"
    patch(workspace, [{"type": "catalog", "value": current}])
    assert e.load(workspace)[2].article_reviewed
    assert e.load(workspace)[3]["catalog"]["version"] == current["version"]
    assert (workspace / "inputs/snapshot.json").read_bytes() == before


def test_targeted_x_model_rewrite_keeps_other_cards_exact(workspace, model):
    complete(workspace)
    first = writing.propose(workspace, "x", "three-cards")
    writing.accept(workspace, first["candidate"], first["revision_id"])
    original = read_json(workspace / "attempts/three-cards.json")["candidate"]
    rewritten = writing.propose(workspace, "x", "one-card", "P02")
    assert len(model) == 4
    candidate = read_json(workspace / "attempts/one-card.json")["candidate"]
    assert candidate[0] == original[0] and candidate[2] == original[2]
    assert len(read_json(workspace / "attempts/one-card.json")["child_attempts"]) == 1
    writing.accept(workspace, rewritten["candidate"], rewritten["revision_id"])


def test_recovery_rejects_runtime_changes_without_request(workspace, model, monkeypatch):
    result = writing.propose(workspace, "outline", "runtime-check")
    path = workspace / "attempts/runtime-check.json"
    attempt = read_json(path)
    attempt["status"] = "response_saved"
    attempt["runtime"]["model"] = "another-model"
    write_json(path, attempt)
    with pytest.raises(RunError) as exc:
        writing.recover(workspace, result["candidate"])
    assert exc.value.code == "RUNTIME_MISMATCH" and len(model) == 1
