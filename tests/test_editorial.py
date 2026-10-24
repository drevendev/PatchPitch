"""Editorial domain contracts. All inference and DEV responses here are MOCK."""
import copy
import json
from pathlib import Path

import pytest

from patchpitch import editorial as e, editorial_generation as writing, editorial_render as rendering
from patchpitch import editorial_x as x, editorial_dev as dev, generator
from patchpitch.run_store import read_json, write_json, RunError, digest
from test_campaigns import catalog_data


@pytest.fixture
def workspace(tmp_path):
    write_json(tmp_path / "facts.json", {"schema_version": 1, "id": "editorial-fixture", "version": "1",
        "product": {"name": "PatchPitch", "description": "Local drafting."}, "audience": "developers",
        "facts": [{"id": "drafts", "text": "PatchPitch prepares local drafts.", "include": True, "kind": "internal", "source_ref": "synthetic test"},
                  {"id": "recovery", "text": "PatchPitch keeps local edits after failure.\n```sh\npatchpitch --help\n```", "include": True, "kind": "internal", "source_ref": "synthetic test"}]})
    catalog = catalog_data()
    catalog["tags"][-1]["tag"] = "#DEVCommunity"
    catalog["tags"][-1]["keywords"] = ["DEV", "article"]
    write_json(tmp_path / "catalog.json", catalog)
    config = {"schema_version": "patchpitch.editorial-job/v1", "campaign_id": "editorial-test", "source": {"kind": "reviewed_fact_pack", "path": "facts.json"},
        "style": "clear", "hashtag_catalog": "catalog.json"}
    write_json(tmp_path / "editorial.json", config)
    root = tmp_path / "work"
    e.initialize(tmp_path / "editorial.json", root)
    return root


def outline():
    return {"title": "My local drafts", "thesis": "Keep local edits", "audience": "developers", "reader_outcome": "Recover work",
        "angle": "A concrete result", "sections": [
            {"id": "S01", "heading": "The problem", "purpose": "Show local drafts", "source_ids": ["C01"]},
            {"id": "S02", "heading": "The result", "purpose": "Keep local edits", "source_ids": ["C02"], "code_refs": ["C02-code-1"]}]}


def patch(root, operations, op=None):
    revision = e.load(root)[2].revision_id
    return e.apply(root, {"operation_id": op or "op-" + digest({"revision": revision, "ops": operations})[:24],
                         "expected_revision_id": revision, "operations": operations})


def planned(root):
    patch(root, [{"type": "outline", "value": outline()}])
    patch(root, [{"type": "review_outline"}, {"type": "review_sources"}])


def complete(root):
    planned(root)
    for i, source in [(1, "C01"), (2, "C02")]:
        patch(root, [{"type": "section", "value": {"id": f"S0{i}", "heading": "The problem" if i == 1 else "The result",
            "blocks": [{"id": f"B0{i}", "kind": "paragraph", "text": "I keep local drafts." if i == 1 else "My local edits survive failure.", "source_ids": [source]}]}}])
    patch(root, [{"type": "metadata", "value": {"description": "A test article about local drafts.", "tags": ["devtools"]}}])
    patch(root, [{"type": "review_article"}])


@pytest.fixture
def model(monkeypatch):
    calls = []
    def answer(path, payload, **kwargs):
        calls.append(copy.deepcopy(payload))
        properties = payload["format"]["properties"]
        if "thesis" in properties:
            result = outline()
        elif "posts" in properties:
            data = json.loads(payload["messages"][0]["content"].split("UNTRUSTED DATA:\n", 1)[1])
            start = ("I prepare", "I review", "I keep")[int(data.get("target_post_id", "P01")[-2:]) - 1]
            result = {"posts": [{"topic": "local drafts", "source_ids": ["C01"], "text": f"{start} local drafts."}]}
        else:
            content = payload["messages"][0]["content"]
            data = json.loads(content.split("UNTRUSTED TASK DATA:\n")[1])
            result = {"paragraphs": [{"text": "I keep local drafts.", "source_ids": data["selected_section"]["source_ids"]}]}
        return {"done": True, "model": "MOCK", "message": {"content": json.dumps(result)}}
    monkeypatch.setattr(generator, "ollama_json", answer)
    return calls


def test_init_dry_run_outline_and_batch_candidates(workspace, model):
    assert e.status(workspace)["status"] == "sources_ready" and not model
    result = writing.propose(workspace, "outline", "outline-one", dry_run=True)
    assert result["model_requests"] == 1 and not model
    first = writing.propose(workspace, "outline", "outline-one")
    assert writing.propose(workspace, "outline", "outline-one") == first and len(model) == 1
    writing.accept(workspace, first["candidate"], first["revision_id"])
    patch(workspace, [{"type": "review_sources"}, {"type": "review_outline"}])
    candidates = writing.draft(workspace, "first-draft")
    assert len(model) == 3
    schema = model[-1]["format"]["$defs"]["ProseParagraph"]
    assert "source_ids" in schema["required"]
    assert schema["properties"]["source_ids"]["items"]["enum"] == ["C02"]
    assert writing.draft(workspace, "first-draft")["candidate"] == candidates["candidate"] and len(model) == 3
    writing.accept(workspace, candidates["candidate"], candidates["revision_id"])
    assert e.status(workspace)["status"] == "draft_ready"
    assert all(s.blocks for s in e.load(workspace)[2].sections)
    assert writing.draft(workspace)["status"] == "draft_completed" and len(model) == 3


def test_cas_idempotence_and_immutable_revision(workspace):
    before = e.load(workspace)[2]
    change = {"operation_id": "set-metadata", "expected_revision_id": before.revision_id,
              "operations": [{"type": "metadata", "value": {"title": "  My exact title  "}}]}
    result = e.apply(workspace, change)
    assert e.apply(workspace, change) == result
    assert e.load(workspace)[2].metadata.title == "  My exact title  "
    assert read_json(workspace / f"revisions/{before.revision_id}.json")["metadata"]["title"] == ""
    with pytest.raises(RunError, match="already used"):
        e.apply(workspace, {**change, "operations": [{"type": "review_sources"}]})
    with pytest.raises(RunError) as exc:
        e.apply(workspace, {**change, "operation_id": "stale"})
    assert exc.value.code == "REVISION_CONFLICT"


def test_targeted_revision_preserves_other_sections_and_rejects_stale(workspace, model):
    complete(workspace)
    before = e.load(workspace)[2]
    second = before.sections[1].model_dump()
    candidate = writing.propose(workspace, "section", "rewrite-one", "S01", "Make it concrete.")
    writing.accept(workspace, candidate["candidate"], candidate["revision_id"])
    after = e.load(workspace)[2]
    assert after.sections[1].model_dump() == second and not after.article_reviewed
    stale = writing.propose(workspace, "section", "rewrite-two", "S01")
    section = e.load(workspace)[2].sections[0].model_dump()
    section["blocks"][0]["text"] = "My manual edit wins."
    patch(workspace, [{"type": "section", "value": section}])
    with pytest.raises(RunError) as exc:
        writing.accept(workspace, stale["candidate"], stale["revision_id"])
    assert exc.value.code == "REVISION_CONFLICT"
    assert e.load(workspace)[2].sections[0].blocks[0].text == "My manual edit wins."


def test_failed_and_locked_attempts_preserve_document(workspace, model, monkeypatch):
    complete(workspace)
    patch(workspace, [{"type": "lock_section", "section_id": "S01", "locked": True}])
    before = e.load(workspace)[2].model_dump()
    with pytest.raises(RunError) as exc:
        writing.propose(workspace, "section", "locked", "S01")
    assert exc.value.code == "SECTION_LOCKED" and not model
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **k: {"done": False, "message": {"content": "unfinished"}})
    with pytest.raises(RunError):
        writing.propose(workspace, "section", "failed", "S02")
    assert e.load(workspace)[2].model_dump() == before
    assert read_json(workspace / "attempts/failed.json")["raw_response"]["done"] is False
    assert e.status(workspace)["request_count"] == 1


@pytest.mark.parametrize("mutation,code", [
    ({"type": "outline", "value": {**outline(), "omissions": {"C01": "skip"}}}, "OUTLINE_COVERAGE"),
    ({"type": "metadata", "value": {"cover_asset_id": "missing"}}, "COVER_INVALID"),
    ({"type": "review_article"}, "ARTICLE_NOT_REVIEWED"),
    ({"type": "unknown"}, "MUTATION_INVALID")])
def test_invalid_mutations_never_advance(workspace, mutation, code):
    before = e.load(workspace)[2].revision_id
    with pytest.raises(RunError) as exc:
        patch(workspace, [mutation])
    assert exc.value.code == code and e.load(workspace)[2].revision_id == before


def test_reorder_delete_and_tombstone_ids(workspace):
    complete(workspace)
    before = e.load(workspace)[2]
    plan = before.outline.model_dump()
    plan["sections"].reverse()
    patch(workspace, [{"type": "outline", "value": plan}])
    assert e.load(workspace)[2].sections[1].blocks == before.sections[0].blocks
    plan["sections"] = [s for s in plan["sections"] if s["id"] != "S01"]
    plan["omissions"] = {"C01": "Owner omitted this topic."}
    patch(workspace, [{"type": "outline", "value": plan}])
    with pytest.raises(RunError) as exc:
        patch(workspace, [{"type": "outline", "value": outline()}])
    assert exc.value.code == "REUSED_ID"


def test_x_url_binding_budget_and_staleness(workspace, model, monkeypatch):
    complete(workspace)
    result = writing.propose(workspace, "x", "x-series")
    writing.accept(workspace, result["candidate"], result["revision_id"])
    root, manifest, doc, inputs = e.load(workspace)
    assert x.export_series(root, manifest, doc)["status"] == "awaiting_public_url"
    url = "https://dev.to/writer/" + "long-title-" * 8 + "abcd"
    monkeypatch.setattr(x, "public_fetch", lambda u: {"body": json.dumps({"id": 42, "url": url, "published_at": "2026-10-24T00:00:00Z"}).encode()})
    x.bind_url(root, url, verify=True)
    _, manifest, doc, _ = e.load(root)
    ready = x.export_series(root, manifest, doc)
    assert ready["status"] == "ready" and len(ready["posts"]) == 3 and len(model) == 3
    assert all(len(p["hashtags"]) == 6 and "#DEVCommunity" in p["hashtags"] for p in ready["posts"])
    assert all(p["length"]["characters"] == len(p["text"]) - len(url) + 23 for p in ready["posts"])
    for bad in [url + "?preview=secret", "http://dev.to/writer/a", "https://localhost/x/y", "https://example.com/a/b"]:
        with pytest.raises(RunError):
            x.bind_url(root, bad)
    patch(root, [{"type": "metadata", "value": {"description": "A different angle."}}])
    assert e.status(root)["x_state"] == "stale"


def test_preview_is_safe_current_and_export_edit_detected(workspace, tmp_path):
    complete(workspace)
    section = e.load(workspace)[2].sections[0].model_dump()
    section["blocks"][0]["text"] = 'My **local** draft <img src=x onerror=alert(1)> [bad](javascript:alert).'
    patch(workspace, [{"type": "section", "value": section}])
    out = tmp_path / "preview"
    rendering.export(workspace, out)
    html = (out / "preview.html").read_text(encoding="utf-8")
    assert "<strong>local</strong>" in html and "&lt;img" in html and 'href="javascript:' not in html
    assert "unsafe-eval" not in html and "voice_bundle" not in html
    assert "My **local**" in (out / "article.md").read_text(encoding="utf-8")
    (out / "article.md").write_text("An external manual edit.", encoding="utf-8")
    with pytest.raises(RunError) as exc:
        rendering.export(workspace, out)
    assert exc.value.code == "EXPORT_CHANGED"


@pytest.fixture
def dev_remote(monkeypatch):
    articles, calls = {}, []
    monkeypatch.setenv("PATCHPITCH_DEV_API_KEY", "mock-key-never-log")
    def request(method, route, data, key):
        calls.append((method, copy.deepcopy(data)))
        value = copy.deepcopy(data["article"])
        identity = 42 if method == "POST" else int(route.rsplit("/", 1)[1])
        articles[identity] = {**value, "id": identity, "published_at": None, "tag_list": value["tags"], "url": "https://dev.to/test/draft"}
        return copy.deepcopy(articles[identity])
    def owned(identity, key):
        if articles[identity].get("published_at"):
            raise RunError("REMOTE_ALREADY_PUBLISHED", "Published", 5)
        return copy.deepcopy(articles[identity])
    monkeypatch.setattr(dev, "request_api", request)
    monkeypatch.setattr(dev, "owned_article", owned)
    return articles, calls


def test_dev_same_draft_remote_conflict_and_explicit_resolution(workspace, dev_remote):
    complete(workspace)
    articles, calls = dev_remote
    first = dev.deliver(workspace)
    assert first["status"] == "remote_draft" and calls[0][1]["article"]["published"] is False
    assert not calls[0][1]["article"]["body_markdown"].startswith("# ")
    assert dev.deliver(workspace) == first and len(calls) == 1
    articles[42]["description"] = "Changed by the author on DEV"
    with pytest.raises(RunError) as exc:
        dev.deliver(workspace)
    assert exc.value.code == "REMOTE_DRAFT_CHANGED" and len(calls) == 1
    observed = dev.inspect(workspace)
    patch(workspace, [{"type": "metadata", "value": {"description": "New local description"}}])
    patch(workspace, [{"type": "review_article"}])
    dev.deliver(workspace, expected_remote_hash=observed["remote_sha256"])
    assert calls[-1][0] == "PUT" and len(articles) == 1
    articles[42]["published_at"] = "2026-10-24T00:00:00Z"
    with pytest.raises(RunError) as exc:
        dev.deliver(workspace)
    assert exc.value.code == "REMOTE_ALREADY_PUBLISHED"


def test_dev_uncertain_write_reconciles_original_then_preserves_new_edit(workspace, dev_remote, monkeypatch):
    complete(workspace)
    original = dev.request_api
    def lost(method, route, data, key):
        original(method, route, data, key)
        raise RunError("DEV_OUTCOME_UNKNOWN", "Lost response", 5)
    monkeypatch.setattr(dev, "request_api", lost)
    with pytest.raises(RunError):
        dev.deliver(workspace)
    patch(workspace, [{"type": "metadata", "value": {"description": "Later local edit"}}])
    patch(workspace, [{"type": "review_article"}])
    monkeypatch.setattr(dev, "request_api", original)
    with pytest.raises(RunError) as exc:
        dev.deliver(workspace)
    assert exc.value.code == "DEV_OUTCOME_UNKNOWN"
    dev.deliver(workspace, existing_id=42)
    assert len(dev_remote[0]) == 1 and dev_remote[0][42]["description"] == "Later local edit"


def test_missing_voice_and_source_fingerprint(workspace):
    root, manifest, doc, inputs = e.load(workspace)
    inputs["sources"]["product"]["name"] = "Changed outside operation"
    write_json(root / "inputs/snapshot.json", inputs)
    with pytest.raises(RunError) as exc:
        e.load(root)
    assert exc.value.code == "EDITORIAL_IDENTITY"


def test_dev_cover_dto_alias_and_transform_are_compared_without_losing_payload():
    expected = {"title": "A title", "description": "A description", "body_markdown": "Body", "tags": ["devtools"],
                "main_image": "https://example.com/cover.png", "ai_disclosure_level": "some_ai"}
    observed = {k: v for k, v in expected.items() if k not in {"main_image", "ai_disclosure_level"}}
    observed["cover_image"] = "https://media2.dev.to/dynamic/image/width=1000/https%3A%2F%2Fexample.com%2Fcover.png"
    assert dev.matches_submitted(observed, expected)
    observed["cover_image"] = "https://example.com/a-different-cover.png"
    assert not dev.matches_submitted(observed, expected)


def test_visual_review_is_explicit_and_rejects_remote_changes(workspace, dev_remote):
    complete(workspace)
    receipt = dev.deliver(workspace)
    assert receipt["remote_preview_reviewed"] is False
    revision = e.load(workspace)[2].revision_id
    assert dev.review_preview(workspace, revision)["status"] == "remote_preview_reviewed"
    dev_remote[0][42]["description"] = "Edited in DEV after viewing"
    with pytest.raises(RunError) as exc:
        dev.review_preview(workspace, revision)
    assert exc.value.code == "REMOTE_DRAFT_CHANGED"


def test_export_preserves_history_when_x_becomes_stale(workspace, model, monkeypatch, tmp_path):
    complete(workspace)
    result = writing.propose(workspace, "x", "export-series")
    writing.accept(workspace, result["candidate"], result["revision_id"])
    url = "https://dev.to/writer/published-article"
    monkeypatch.setattr(x, "public_fetch", lambda u: {"body": json.dumps({"id": 42, "url": url, "published_at": "2026-10-24"}).encode()})
    x.bind_url(workspace, url, verify=True)
    out = tmp_path / "before"
    rendering.export(workspace, out)
    original = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    patch(workspace, [{"type": "metadata", "value": {"description": "A changed article"}}])
    with pytest.raises(RunError) as exc:
        rendering.export(workspace, out)
    assert exc.value.code == "EXPORT_STALE"
    assert original == {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    fresh = tmp_path / "after"
    rendering.export(workspace, fresh)
    assert not (fresh / "x").exists()
    assert read_json(fresh / "export.json")["x_state"] == "stale"


def test_public_url_must_match_delivered_article(workspace, dev_remote, monkeypatch):
    complete(workspace)
    dev.deliver(workspace)
    url = "https://dev.to/writer/a-different-article"
    monkeypatch.setattr(x, "public_fetch", lambda u: {"body": json.dumps({"id": 43, "url": url, "published_at": "2026-10-24"}).encode()})
    with pytest.raises(RunError) as exc:
        x.bind_url(workspace, url, verify=True)
    assert exc.value.code == "ARTICLE_ID_MISMATCH"
    assert e.load(workspace)[1]["public_url"] is None
