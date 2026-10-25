"""Regression cases found while reviewing PR 92 against the editorial specification."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from patchpitch import editorial as e, editorial_generation as writing, editorial_x as x
from patchpitch import editorial_dev as dev, editorial_render as rendering, generator, hashtags
from patchpitch.app import app
from patchpitch.run_store import RunError, read_json
from test_editorial import workspace, model, complete, planned, patch, dev_remote
from test_editorial_media import FIXTURES


def series(workspace):
    result = writing.propose(workspace, "x", "review-series")
    writing.accept(workspace, result["candidate"], result["revision_id"])
    return result


def test_delivery_rejects_the_stale_editor_before_any_remote_write(workspace, dev_remote):
    complete(workspace)
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post("/api/editorial", json={"action": "deliver", "work": str(workspace),
        "expected_revision_id": "R" + "0" * 64})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"
    assert not dev_remote[1]


def test_old_ui_cannot_omit_the_delivery_revision(workspace, dev_remote):
    complete(workspace)
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.post("/api/editorial", json={"action": "deliver", "work": str(workspace)})
    assert response.status_code == 422 and response.json()["error"]["code"] == "ARGUMENT_ERROR"
    assert not dev_remote[1]


def test_cover_removal_is_sent_and_unexpected_remote_cover_is_detected(workspace, dev_remote):
    complete(workspace)
    patch(workspace, [{"type": "import_media", "id": "cover", "path": str(FIXTURES / "editorial-image.png"),
                       "provenance": "Synthetic fixture", "alt": "Test cover"}])
    patch(workspace, [{"type": "asset", "id": "cover", "value": {"public_url": "https://example.com/cover.png"}},
                      {"type": "metadata", "value": {"cover_asset_id": "cover"}}])
    patch(workspace, [{"type": "review_article"}])
    dev.deliver(workspace)
    patch(workspace, [{"type": "metadata", "value": {"cover_asset_id": None}}])
    patch(workspace, [{"type": "review_article"}])
    dev.deliver(workspace)
    assert "main_image" in dev_remote[1][-1][1]["article"]
    assert dev_remote[1][-1][1]["article"]["main_image"] is None
    dev_remote[0][42]["main_image"] = "https://example.com/remote-edit.png"
    with pytest.raises(RunError) as error:
        dev.deliver(workspace)
    assert error.value.code == "REMOTE_DRAFT_CHANGED"


def test_multiple_batch_retries_keep_the_successful_retry(workspace, model, monkeypatch):
    planned(workspace)
    plan = e.load(workspace)[2].outline.model_dump()
    plan["sections"].append({"id": "S03", "heading": "One more example", "purpose": "Another angle", "source_ids": ["C01"]})
    patch(workspace, [{"type": "outline", "value": plan}])
    patch(workspace, [{"type": "review_outline"}])
    original, calls = generator.ollama_json, []
    def fail_once(path, payload, **kwargs):
        data = json.loads(payload["messages"][0]["content"].split("UNTRUSTED TASK DATA:\n", 1)[1])
        sid = data["selected_section"]["id"]
        calls.append(sid)
        if sid in {"S01", "S02"} and calls.count(sid) == 1:
            return {"done": False, "message": {"content": "interrupted"}}
        return original(path, payload, **kwargs)
    monkeypatch.setattr(generator, "ollama_json", fail_once)
    with pytest.raises(RunError):
        writing.draft(workspace, "multi-retry")
    with pytest.raises(RunError):
        writing.draft(workspace, "multi-retry", retry_failed=True)
    result = writing.draft(workspace, "multi-retry", retry_failed=True)
    assert calls == ["S01", "S01", "S02", "S02", "S03"]
    writing.accept(workspace, result["candidate"], result["revision_id"])


def test_repeating_a_rejected_batch_never_revives_it(workspace, model):
    planned(workspace)
    result = writing.draft(workspace, "rejected-batch")
    writing.reject(workspace, result["candidate"])
    before = (workspace / "attempts/rejected-batch.json").read_bytes()
    with pytest.raises(RunError) as error:
        writing.draft(workspace, "rejected-batch")
    assert error.value.code == "CANDIDATE_NOT_READY"
    assert (workspace / "attempts/rejected-batch.json").read_bytes() == before and len(model) == 2


def test_expired_x_evidence_does_not_block_the_article_preview(workspace, model, monkeypatch, tmp_path):
    complete(workspace)
    series(workspace)
    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(timezone.utc) + timedelta(days=400)
    monkeypatch.setattr(hashtags, "datetime", Later)
    root, manifest, doc, _ = e.load(workspace)
    assert x.export_series(root, manifest, doc)["status"] == "blocked"
    assert e.status(root)["x_state"] == "blocked"
    out = tmp_path / "expired-evidence-preview"
    rendering.export(root, out)
    assert (out / "preview.html").is_file() and not (out / "x").exists()
    assert read_json(out / "export.json")["x_state"] == "blocked"


def test_accept_x_checks_the_catalog_dependency(workspace, model):
    complete(workspace)
    result = writing.propose(workspace, "x", "old-catalog-series")
    # Even a restored article revision must not allow a proposal from another catalog.
    root, manifest, doc, inputs = e.load(workspace)
    attempt = read_json(root / "attempts/old-catalog-series.json")
    attempt["catalog_sha256"] = "0" * 64
    with pytest.raises(RunError) as error:
        x.accept_series(root, attempt, result["revision_id"], "accept-old-catalog")
    assert error.value.code == "REVISION_CONFLICT"
    assert e.load(root)[1]["x_series"] is None


def test_dev_markdown_cannot_activate_html_liquid_or_untyped_headings(workspace):
    complete(workspace)
    section = e.load(workspace)[2].sections[0].model_dump()
    section["blocks"][0]["text"] = '**Useful** [docs](https://example.com/docs)\n# Hidden heading\n<iframe src="https://example.com"></iframe> {% youtube abc %}'
    patch(workspace, [{"type": "section", "value": section}])
    _, _, doc, inputs = e.load(workspace)
    body = rendering.body_markdown(doc, inputs)
    assert "**Useful**" in body and "[docs](https://example.com/docs)" in body
    assert '<iframe' not in body and '{% youtube' not in body and '\n# Hidden heading' not in body


def test_public_media_markup_counts_toward_the_body_limit(workspace):
    complete(workspace)
    patch(workspace, [{"type": "import_media", "id": "image", "path": str(FIXTURES / "editorial-image.png"),
                      "provenance": "Synthetic fixture", "alt": "Test image"}])
    section = e.load(workspace)[2].sections[0].model_dump()
    section["blocks"].append({"id": "Bimage", "kind": "media", "asset_id": "image"})
    patch(workspace, [{"type": "section", "value": section}])
    before = e.load(workspace)[2].revision_id
    with pytest.raises(RunError) as error:
        patch(workspace, [{"type": "asset", "id": "image", "value": {"public_url": "https://example.com/" + "a" * 32000}}])
    assert error.value.code == "ARTICLE_LENGTH" and e.load(workspace)[2].revision_id == before


def test_locked_section_rejects_changes_to_its_writing_instructions(workspace):
    complete(workspace)
    patch(workspace, [{"type": "lock_section", "section_id": "S01", "locked": True}])
    plan = e.load(workspace)[2].outline.model_dump()
    plan["sections"][0]["purpose"] = "A different instruction"
    with pytest.raises(RunError) as error:
        patch(workspace, [{"type": "outline", "value": plan}])
    assert error.value.code == "SECTION_LOCKED"


def test_x_batch_reuses_successful_retry_after_another_card_fails(workspace, model, monkeypatch):
    complete(workspace)
    original, calls = generator.ollama_json, []
    def fail_once(path, payload, **kwargs):
        data = json.loads(payload["messages"][0]["content"].split("UNTRUSTED DATA:\n", 1)[1])
        pid = data["target_post_id"]
        calls.append(pid)
        if pid in {"P01", "P02"} and calls.count(pid) == 1:
            return {"done": False, "message": {"content": "interrupted"}}
        return original(path, payload, **kwargs)
    monkeypatch.setattr(generator, "ollama_json", fail_once)
    for retry in (False, True):
        with pytest.raises(RunError):
            writing.propose(workspace, "x", "x-multi-retry", retry_failed=retry)
    result = writing.propose(workspace, "x", "x-multi-retry", retry_failed=True)
    assert calls == ["P01", "P01", "P02", "P02", "P03"]
    writing.accept(workspace, result["candidate"], result["revision_id"])


def test_expired_tags_preserve_old_export_without_leaving_copy_ready_files(workspace, model, monkeypatch, tmp_path):
    complete(workspace)
    series(workspace)
    url = "https://dev.to/writer/a-published-article"
    monkeypatch.setattr(x, "public_fetch", lambda u: {"body": json.dumps({"id": 42, "url": url, "published_at": "2026-10-24"}).encode()})
    x.bind_url(workspace, url, verify=True)
    out = tmp_path / "ready-copy"
    rendering.export(workspace, out)
    old = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    def no_evidence(*args, **kwargs):
        raise RunError("HASHTAGS_INSUFFICIENT_EVIDENCE", "Expired observations", 4)
    monkeypatch.setattr(x, "decisions", no_evidence)
    with pytest.raises(RunError) as error:
        rendering.export(workspace, out)
    assert error.value.code == "EXPORT_STALE"
    assert old == {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    fresh = tmp_path / "article-only"
    rendering.export(workspace, fresh)
    assert (fresh / "article.md").is_file() and not (fresh / "x").exists()


def test_unfinished_batch_cannot_mix_runtime_or_revision(workspace, model, monkeypatch):
    planned(workspace)
    original = generator.ollama_json
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **k: {"done": False})
    with pytest.raises(RunError):
        writing.draft(workspace, "frozen-runtime")
    monkeypatch.setattr(generator, "ollama_json", original)
    runtime = writing.runtime
    monkeypatch.setattr(writing, "runtime", lambda: {**runtime(), "model": "different-model"})
    with pytest.raises(RunError) as error:
        writing.draft(workspace, "frozen-runtime", retry_failed=True)
    assert error.value.code == "RUNTIME_MISMATCH" and not model
    monkeypatch.setattr(writing, "runtime", runtime)
    patch(workspace, [{"type": "metadata", "value": {"description": "An intervening change"}}])
    with pytest.raises(RunError) as error:
        writing.draft(workspace, "frozen-runtime", retry_failed=True)
    assert error.value.code == "REVISION_CONFLICT" and not model


def test_dry_run_does_not_reserve_batch_operations(workspace, model):
    planned(workspace)
    before = (workspace / "manifest.json").read_bytes()
    assert writing.draft(workspace, "dry-reservations", dry_run=True)["model_requests"] == 2
    assert (workspace / "manifest.json").read_bytes() == before and not model


def test_x_prompt_excludes_facts_omitted_from_the_article(workspace, model):
    complete(workspace)
    plan = e.load(workspace)[2].outline.model_dump()
    plan["sections"] = plan["sections"][:1]
    plan["omissions"] = {"C02": "Not part of this story"}
    patch(workspace, [{"type": "outline", "value": plan}])
    patch(workspace, [{"type": "review_outline"}, {"type": "review_article"}])
    root, _, doc, inputs = e.load(workspace)
    payload, _ = x.x_payload(root, doc, inputs, "P01", fresh_post=True)
    data = json.loads(payload["messages"][0]["content"].split("UNTRUSTED DATA:\n", 1)[1])
    assert set(data["selected_facts"]) == {"C01"}


@pytest.mark.parametrize("text", ["*", "**", "`", "**\n**"])
def test_literal_format_delimiters_are_not_lost(text):
    assert rendering.inline(text) == text.replace("\n", "<br>")
    assert rendering.markdown_inline(text)


def test_candidate_acceptance_rechecks_expired_evidence(workspace, model, monkeypatch):
    complete(workspace)
    result = writing.propose(workspace, "x", "expires-before-acceptance")
    monkeypatch.setattr(x, "decisions", lambda *a, **k: (_ for _ in ()).throw(
        RunError("HASHTAGS_INSUFFICIENT_EVIDENCE", "Expired evidence", 4)))
    with pytest.raises(RunError) as error:
        writing.accept(workspace, result["candidate"], result["revision_id"])
    assert error.value.code == "HASHTAGS_INSUFFICIENT_EVIDENCE"
    assert e.load(workspace)[1]["x_series"] is None


def test_liquid_in_exact_code_is_preserved_but_blocks_dev_delivery(workspace):
    from patchpitch.editorial_models import Block
    complete(workspace)
    _, _, doc, inputs = e.load(workspace)
    source = '```text\n{% youtube abc %}\n```'
    inputs["snippets"]["C02-code-1"]["text"] = source
    doc.sections[1].blocks.append(Block(id="Bexact", kind="code", snippet_id="C02-code-1", source_ids=["C02"]))
    assert source in rendering.body_markdown(doc, inputs)
    with pytest.raises(RunError) as error:
        dev.payload(doc, inputs)
    assert error.value.code == "DEV_UNSUPPORTED_MARKUP"


def test_delivery_plan_matches_outgoing_payload_and_does_not_use_network(workspace, dev_remote):
    from patchpitch.run_store import digest
    complete(workspace)
    status = e.status(workspace, include_document=True)
    _, _, doc, inputs = e.load(workspace)
    plan = status["delivery_preview"]
    assert plan["revision_id"] == doc.revision_id and plan["article_id"] is None and not dev_remote[1]
    assert plan["payload_sha256"] == digest(dev.payload(doc, inputs)) and plan["published"] is False


def test_older_batch_metadata_still_checks_the_child_runtime(workspace, model, monkeypatch):
    from patchpitch.run_store import write_json
    planned(workspace)
    original = generator.ollama_json
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **k: {"done": False})
    with pytest.raises(RunError):
        writing.draft(workspace, "older-batch")
    manifest = read_json(workspace / "manifest.json")
    manifest["operations"]["older-batch"].pop("runtime")
    write_json(workspace / "manifest.json", manifest)
    child = read_json(workspace / "attempts/older-batch-S01.json")
    child["runtime"]["model"] = "older-runtime-model"
    write_json(workspace / "attempts/older-batch-S01.json", child)
    monkeypatch.setattr(generator, "ollama_json", original)
    with pytest.raises(RunError) as error:
        writing.draft(workspace, "older-batch", retry_failed=True)
    assert error.value.code == "RUNTIME_MISMATCH" and not model


@pytest.mark.parametrize("kind", ["draft", "x"])
def test_rejected_child_cannot_be_accepted_indirectly_by_its_batch(workspace, model, kind):
    complete(workspace) if kind == "x" else planned(workspace)
    result = writing.propose(workspace, "x", "reject-child") if kind == "x" else writing.draft(workspace, "reject-child")
    child = read_json(workspace / "attempts/reject-child.json")["child_attempts"][0]
    writing.reject(workspace, child)
    before = e.load(workspace)[2].revision_id
    with pytest.raises(RunError) as error:
        writing.accept(workspace, result["candidate"], result["revision_id"])
    assert error.value.code == "CANDIDATE_NOT_READY"
    assert e.load(workspace)[2].revision_id == before and e.load(workspace)[1]["x_series"] is None


def test_committed_acceptance_survives_marker_crash_and_later_edit(workspace, model, monkeypatch):
    planned(workspace)
    result = writing.draft(workspace, "accept-marker-crash")
    original = writing.write_json
    def crash(path, value):
        if path.name == "accept-marker-crash.json" and value.get("status") == "accepted":
            raise OSError("simulated failure after the manifest commit")
        return original(path, value)
    monkeypatch.setattr(writing, "write_json", crash)
    with pytest.raises(OSError):
        writing.accept(workspace, result["candidate"], result["revision_id"])
    assert all(s.blocks for s in e.load(workspace)[2].sections)
    assert writing.recover(workspace, result["candidate"])["status"] == "accepted"
    assert all(a["status"] == "accepted" for a in e.status(workspace, include_document=True)["attempts"])
    for candidate in ["accept-marker-crash", "accept-marker-crash-S01"]:
        with pytest.raises(RunError) as error:
            writing.reject(workspace, candidate)
        assert error.value.code == "CANDIDATE_NOT_READY"
    patch(workspace, [{"type": "metadata", "value": {"description": "A newer edit"}}])
    latest = e.load(workspace)[2].revision_id
    monkeypatch.setattr(writing, "write_json", original)
    writing.accept(workspace, result["candidate"], result["revision_id"])
    assert e.load(workspace)[2].revision_id == latest
    assert read_json(workspace / "attempts/accept-marker-crash.json")["status"] == "accepted"
