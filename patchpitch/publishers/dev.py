"""Forem draft delivery with saved receipts and explicit unknown-outcome recovery."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from ..campaign_export import current_result, load_run
from ..campaigns import now
from ..run_store import FileLock, RunError, digest, read_json, write_json


def request_api(method, route, payload, key):
    request = urllib.request.Request("https://dev.to/api" + route, method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"api-key": key, "Accept": "application/vnd.forem.api-v1+json", "Content-Type": "application/json", "User-Agent": "PatchPitch/0.3"})
    # Fixed host, no redirect to an untrusted credential recipient.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Oversized response")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        code = "DEV_REQUEST_REJECTED" if exc.code in {400, 401, 403, 404, 405, 413, 415, 422, 429} else "DEV_HTTP_ERROR"
        raise RunError(code, f"DEV returned HTTP {exc.code}; the response body and credentials were not logged.", 5) from exc
    except (OSError, ValueError) as exc:
        raise RunError("DEV_OUTCOME_UNKNOWN" if method in {"POST", "PUT"} else "DEV_UNAVAILABLE",
                       "No verifiable DEV response was received. Reconcile an uncertain write with --existing-id.", 5) from exc


def owned_article(article_id, key):
    # Authenticated own articles establish ownership and current publication
    # status, including private drafts that a public GET cannot retrieve.
    for page in range(1, 21):
        articles = request_api("GET", f"/articles/me/all?page={page}&per_page=100", None, key)
        if not isinstance(articles, list):
            raise RunError("DEV_INVALID_RESPONSE", "DEV did not return an owned-article list.", 5)
        for article in articles:
            if article.get("id") == article_id:
                if article.get("published_at") or article.get("published") is True:
                    raise RunError("REMOTE_ALREADY_PUBLISHED", "Draft delivery does not change an already published article.", 5)
                return article
        if len(articles) < 100:
            break
    raise RunError("DEV_ARTICLE_NOT_OWNED", "Article was not found in the bounded list of your own articles.", 5)


def deliver(path, target_id=None, existing_id=None):
    path = Path(path).resolve()
    with FileLock(path / ".run.lock"):
        path, snap, manifest = load_run(path)
        targets = [t for t in snap["job"]["targets"] if t["channel"] == "dev" and (target_id is None or t["id"] == target_id)]
        if len(targets) != 1:
            raise RunError("DEV_TARGET_AMBIGUOUS", "Select exactly one DEV target with --target.")
        target = targets[0]
        if manifest["targets"][target["id"]]["status"] != "succeeded":
            raise RunError("TARGET_NOT_READY", "The selected DEV target has no completed article.", 4)
        _, current = current_result(path, snap, target)
        draft = current["draft"]
        metadata = read_json(path / "outputs" / target["id"] / "article.json", 200_000)
        disclosure = metadata.get("ai_disclosure_level", "fully_autonomous")
        if disclosure not in {"no_ai", "some_ai", "fully_autonomous"}:
            raise RunError("INVALID_AI_DISCLOSURE", "Select a valid DEV AI disclosure level in article.json.", 4)
        # Public payload is a narrow allowlist, never an entire result/session.
        article = {"title": draft["title"], "description": draft["description"], "body_markdown": draft["text"],
                   "tags": list(draft["tags"]), "published": False, "ai_disclosure_level": disclosure}
        content_hash = digest(article)
        receipt_path = path / "outputs" / target["id"] / "delivery.json"
        previous = read_json(receipt_path) if receipt_path.exists() else None
        if existing_id is not None and existing_id <= 0:
            raise RunError("INVALID_ARTICLE_ID", "Article ID must be positive.")
        if previous and previous.get("status") in {"sending", "delivery_unknown"} and existing_id is None:
            raise RunError("DEV_OUTCOME_UNKNOWN", "A previous write is uncertain; reconcile it with --existing-id before delivery.", 5)
        article_id = existing_id if existing_id is not None else (previous or {}).get("article_id")
        key = os.environ.get("PATCHPITCH_DEV_API_KEY", "")
        if not key:
            raise RunError("DEV_KEY_MISSING", "Set PATCHPITCH_DEV_API_KEY before explicit draft delivery.", 5)
        if article_id:
            owned = owned_article(article_id, key)
            if existing_id is not None:
                # Reconciliation must identify the exact content; changing an
                # unrelated owned article requires a different explicit workflow.
                old = {"title": owned.get("title"), "description": owned.get("description", ""),
                       "body_markdown": owned.get("body_markdown"),
                       "tags": list(owned.get("tag_list", [])), "published": False,
                       "ai_disclosure_level": owned.get("ai_disclosure_level")}
                expected_hash = (previous or {}).get("content_sha256", content_hash)
                expected = (previous or {}).get("article")
                if expected is None and content_hash == expected_hash:
                    expected = article  # Receipts written before payload snapshots.
                if not isinstance(expected, dict) or digest(expected) != expected_hash:
                    raise RunError("DEV_RECONCILIATION_MISMATCH", "Cannot reconstruct the uncertain payload; restore its local publication files before reconciliation.", 5)
                expected = dict(expected)
                # The owned-article DTO can omit disclosure. Compare all visible
                # content, then PUT the explicit desired disclosure on this ID.
                # A missing field is unknown, never an invented default value.
                if old["ai_disclosure_level"] is None:
                    del old["ai_disclosure_level"]
                    expected.pop("ai_disclosure_level", None)
                if digest(old) != digest(expected):
                    raise RunError("DEV_RECONCILIATION_MISMATCH", "The owned draft content does not match the uncertain delivery.", 5)
            if previous and previous.get("status") == "remote_draft" and previous.get("content_sha256") == content_hash and existing_id is None:
                return previous
        receipt = {"status": "sending", "article_id": article_id, "content_sha256": content_hash,
                   "article": article, "recorded_at": now()}
        write_json(receipt_path, receipt)
        try:
            response = request_api("PUT" if article_id else "POST", f"/articles/{article_id}" if article_id else "/articles",
                                   {"article": article}, key)
            if not isinstance(response, dict) or type(response.get("id")) is not int:
                raise RunError("DEV_OUTCOME_UNKNOWN", "DEV returned an unverifiable draft response.", 5)
            if response.get("published_at") or response.get("published") is True:
                raise RunError("DEV_OUTCOME_UNKNOWN", "DEV returned an unexpected publication status; inspect the remote article.", 5)
        except RunError as exc:
            # A server error can happen after committing the remote write.
            receipt["status"] = "delivery_failed" if exc.code == "DEV_REQUEST_REJECTED" else "delivery_unknown"
            write_json(receipt_path, receipt)
            raise
        receipt.update(status="remote_draft", article_id=response["id"], url=response.get("url"), recorded_at=now())
        write_json(receipt_path, receipt)
        return receipt
