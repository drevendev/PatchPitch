"""Draft-only delivery; these tests never contact DEV."""
import copy
import pytest

from test_campaigns import job_files, transport
from patchpitch import campaigns
from patchpitch.publishers import dev
from patchpitch.run_store import RunError, read_json, write_json

ORIGINAL_REQUEST_API = dev.request_api


@pytest.fixture
def remote(monkeypatch):
    articles, calls = {}, []
    def api(method, route, payload, key):
        assert key == "test-key-never-export"
        calls.append((method, route, copy.deepcopy(payload)))
        if method == "GET":
            return list(copy.deepcopy(articles).values())
        body = payload["article"]
        assert body["published"] is False
        assert set(body) == {"title", "description", "body_markdown", "tags", "published", "ai_disclosure_level"}
        assert body["ai_disclosure_level"] in {"no_ai", "some_ai", "fully_autonomous"}
        identity = 100 if method == "POST" else int(route.rsplit("/", 1)[-1])
        assert isinstance(body["tags"], list)
        articles[identity] = {**body, "tag_list": list(body["tags"]), "id": identity, "url": "https://dev.to/test/draft", "published_at": None}
        return copy.deepcopy(articles[identity])
    monkeypatch.setenv("PATCHPITCH_DEV_API_KEY", "test-key-never-export")
    monkeypatch.setattr(dev, "request_api", api)
    return calls, articles


def test_create_repeat_and_update_one_draft(job_files, transport, remote):
    job, out, _ = job_files
    campaigns.run(job, out)
    calls, articles = remote
    result = dev.deliver(out)
    assert result["status"] == "remote_draft" and result["article_id"] == 100
    assert dev.deliver(out)["article_id"] == 100
    assert [c[0] for c in calls] == ["POST", "GET"]
    (out / "outputs/dev/article.md").write_text("Edited local publication.\n", encoding="utf-8")
    dev.deliver(out)
    assert calls[-1][0] == "PUT" and articles[100]["body_markdown"] == "Edited local publication."
    assert "test-key-never-export" not in (out / "outputs/dev/delivery.json").read_text()
    assert len(transport) == 5  # Deliver never invokes inference.


def test_published_draft_is_never_unpublished(job_files, transport, remote):
    job, out, _ = job_files
    campaigns.run(job, out)
    calls, articles = remote
    dev.deliver(out)
    articles[100]["published_at"] = "2026-10-22T10:00:00Z"
    with pytest.raises(RunError) as exc:
        dev.deliver(out)
    assert exc.value.code == "REMOTE_ALREADY_PUBLISHED" and calls[-1][0] == "GET"


def test_unknown_post_outcome_requires_reconciliation(job_files, transport, remote, monkeypatch):
    job, out, _ = job_files
    campaigns.run(job, out)
    api = dev.request_api
    def lost_response(method, route, payload, key):
        response = api(method, route, payload, key)
        if method == "POST":
            raise RunError("DEV_OUTCOME_UNKNOWN", "Synthetic lost response", 5)
        return response
    monkeypatch.setattr(dev, "request_api", lost_response)
    with pytest.raises(RunError):
        dev.deliver(out)
    assert read_json(out / "outputs/dev/delivery.json")["status"] == "delivery_unknown"
    with pytest.raises(RunError):
        dev.deliver(out)
    assert len(remote[0]) == 1
    monkeypatch.setattr(dev, "request_api", api)
    assert dev.deliver(out, existing_id=100)["status"] == "remote_draft"
    assert sum(c[0] == "POST" for c in remote[0]) == 1


def test_wrong_article_content_and_missing_key(job_files, transport, remote, monkeypatch):
    job, out, _ = job_files
    campaigns.run(job, out)
    calls, articles = remote
    articles[100] = {"id": 100, "title": "Unrelated draft", "body_markdown": "Another article", "tag_list": []}
    with pytest.raises(RunError) as exc:
        dev.deliver(out, existing_id=100)
    assert exc.value.code == "DEV_RECONCILIATION_MISMATCH"
    monkeypatch.delenv("PATCHPITCH_DEV_API_KEY")
    with pytest.raises(RunError) as exc:
        dev.deliver(out)
    assert exc.value.code == "DEV_KEY_MISSING" and calls[-1][0] == "GET"


def test_definite_auth_rejection_can_retry_after_fixing_key(job_files, transport, remote, monkeypatch):
    import urllib.error
    from types import SimpleNamespace
    api = dev.request_api
    def reject(request, **kwargs):
        raise urllib.error.HTTPError(request.full_url, 401, "private response", {}, None)
    with monkeypatch.context() as scoped:
        scoped.setattr(dev.urllib.request, "build_opener", lambda *a, **k: SimpleNamespace(open=reject))
        with pytest.raises(RunError) as exc:
            ORIGINAL_REQUEST_API("POST", "/articles", {"article": {}}, "secret-not-for-output")
        assert exc.value.code == "DEV_REQUEST_REJECTED" and "secret-not-for-output" not in exc.value.message
    job, out, _ = job_files
    campaigns.run(job, out)
    def denied(*args, **kwargs):
        raise RunError("DEV_REQUEST_REJECTED", "DEV returned HTTP 401", 5)
    monkeypatch.setattr(dev, "request_api", denied)
    with pytest.raises(RunError):
        dev.deliver(out)
    assert read_json(out / "outputs/dev/delivery.json")["status"] == "delivery_failed"
    monkeypatch.setattr(dev, "request_api", api)
    assert dev.deliver(out)["status"] == "remote_draft"


@pytest.mark.parametrize("disclosure", ["no_ai", "some_ai", "fully_autonomous"])
@pytest.mark.parametrize("lost_method", ["POST", "PUT"])
def test_reconcile_omitted_disclosure_and_preserve_later_edits(job_files, transport, remote, monkeypatch, disclosure, lost_method):
    job, out, _ = job_files
    campaigns.run(job, out)
    metadata_path = out / "outputs/dev/article.json"
    metadata = read_json(metadata_path)
    metadata["ai_disclosure_level"] = disclosure
    write_json(metadata_path, metadata)
    if lost_method == "PUT":
        dev.deliver(out)
        (out / "outputs/dev/article.md").write_text("First revision before lost PUT.\n", encoding="utf-8")
    api = dev.request_api
    def lost(method, route, payload, key):
        response = api(method, route, payload, key)
        if method == "GET":
            for item in response:
                item.pop("ai_disclosure_level", None)
        if method == lost_method:
            raise RunError("DEV_OUTCOME_UNKNOWN", "Synthetic lost write response", 5)
        return response
    monkeypatch.setattr(dev, "request_api", lost)
    with pytest.raises(RunError):
        dev.deliver(out)
    (out / "outputs/dev/article.md").write_text("Later explicit editorial change.\n", encoding="utf-8")
    def omit(method, route, payload, key):
        response = api(method, route, payload, key)
        if method == "GET":
            for item in response:
                item.pop("ai_disclosure_level", None)
        return response
    monkeypatch.setattr(dev, "request_api", omit)
    assert dev.deliver(out, existing_id=100)["article_id"] == 100
    assert remote[1][100]["ai_disclosure_level"] == disclosure
    assert remote[1][100]["body_markdown"] == "Later explicit editorial change."
    assert sum(c[0] == "POST" for c in remote[0]) == 1


def test_reconciliation_rejects_visible_disclosure_mismatch(job_files, transport, remote):
    job, out, _ = job_files
    campaigns.run(job, out)
    dev.deliver(out)
    remote[1][100]["ai_disclosure_level"] = "no_ai"
    with pytest.raises(RunError, match="does not match"):
        dev.deliver(out, existing_id=100)
    assert remote[0][-1][0] == "GET"


def test_legacy_receipt_reconciles_missing_disclosure(job_files, transport, remote, monkeypatch):
    job, out, _ = job_files
    campaigns.run(job, out)
    dev.deliver(out)
    receipt_path = out / "outputs/dev/delivery.json"
    receipt = read_json(receipt_path)
    receipt.pop("article")
    receipt["status"] = "delivery_unknown"
    write_json(receipt_path, receipt)
    remote[1][100].pop("ai_disclosure_level")
    assert dev.deliver(out, existing_id=100)["status"] == "remote_draft"
