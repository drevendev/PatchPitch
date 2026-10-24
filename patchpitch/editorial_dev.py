"""Draft-only editorial delivery with remote-edit conflicts and uncertain-write recovery."""
import os

from .editorial import load, status, check_document
from .editorial_media import media_errors, public_fetch
from .editorial_render import body_markdown
from .publishers.dev import request_api, owned_article
from .run_store import FileLock, RunError, digest, read_json, write_json
from .campaigns import now


def cover_identity(value):
    """Forem's DTO can expose the submitted main_image as a transformed cover_image."""
    from urllib.parse import urlsplit, unquote
    if value == "":
        return None
    if isinstance(value, str) and urlsplit(value).hostname == "media2.dev.to":
        lower = value.lower()
        index = lower.rfind("/https%3a")
        if index >= 0:
            return unquote(value[index + 1:])
    return value


def payload(doc, inputs):
    import re
    body = body_markdown(doc, inputs, public=True)
    if body.lstrip().startswith("---"):
        raise RunError("DEV_FRONT_MATTER", "Import front matter into metadata before delivery.", 4)
    if re.search(r"\{[%{]", body):
        raise RunError("DEV_UNSUPPORTED_MARKUP", "Exact source code contains Liquid delimiters. Review a safe DEV representation before delivery; the source is preserved.", 4)
    value = {"title": doc.metadata.title, "description": doc.metadata.description, "body_markdown": body,
        "tags": doc.metadata.tags, "published": False, "ai_disclosure_level": doc.metadata.ai_disclosure_level,
        "main_image": None}
    if doc.metadata.cover_asset_id:
        value["main_image"] = next(a.public_url for a in doc.assets if a.id == doc.metadata.cover_asset_id)
    return value


def observable(article, expected):
    if any(key not in article for key in ("title", "body_markdown")):
        raise RunError("REMOTE_STATE_UNKNOWN", "DEV did not expose enough draft content for safe comparison.", 5)
    value = {"title": article["title"], "description": article.get("description", ""),
        "body_markdown": article["body_markdown"], "tags": sorted(article.get("tag_list", article.get("tags", [])))}
    # Omitted disclosure is unknown, and is still explicitly sent on every PUT.
    if article.get("ai_disclosure_level") is not None:
        value["ai_disclosure_level"] = article["ai_disclosure_level"]
    if "main_image" in expected or "main_image" in article or "cover_image" in article:
        if "main_image" not in article and "cover_image" not in article:
            raise RunError("REMOTE_STATE_UNKNOWN", "DEV did not expose the cover for comparison.", 5)
        value["main_image"] = cover_identity(article.get("main_image", article.get("cover_image")))
    return value


def matches_submitted(remote, expected):
    actual = observable(remote, expected)
    wanted = {k: expected.get(k) if k == "main_image" else expected[k] for k in actual}
    wanted["tags"] = sorted(wanted["tags"])
    if "main_image" in wanted:
        wanted["main_image"] = cover_identity(wanted["main_image"])
    return digest(actual) == digest(wanted)


def delivery_preview(doc, inputs, receipt=None):
    """Show exactly what local revision/target a delivery would use, without a key/network."""
    result = {"revision_id": doc.revision_id, "title": doc.metadata.title,
              "article_id": (receipt or {}).get("article_id"), "payload_sha256": None, "published": False}
    try:
        result["payload_sha256"] = digest(payload(doc, inputs))
    except RunError as exc:
        result["error"] = exc.as_dict()
    return result


def inspect(work):
    root, manifest, doc, inputs = load(work)
    receipt = read_json(root / "receipts/dev.json")
    key = os.environ.get("PATCHPITCH_DEV_API_KEY", "")
    if not key:
        raise RunError("DEV_KEY_MISSING", "Set PATCHPITCH_DEV_API_KEY for explicit DEV operations.", 5)
    if not receipt.get("article_id"):
        raise RunError("DEV_OUTCOME_UNKNOWN", "Reconcile the uncertain creation with its existing article ID first.", 5)
    remote = owned_article(receipt["article_id"], key)
    seen = observable(remote, receipt["article"])
    result = {"status": "remote_inspected", "article_id": receipt["article_id"], "remote_sha256": digest(seen), "remote": seen,
              "local_payload": payload(doc, inputs), "local_revision_id": doc.revision_id}
    write_json(root / "receipts/remote-inspection.json", result)
    return result


def deliver(work, existing_id=None, expected_remote_hash=None, preflight=False, expected_revision_id=None):
    from pathlib import Path
    root = Path(work).resolve()
    with FileLock(root / ".editorial.lock"):
        root, manifest, doc, inputs = load(root)
        if expected_revision_id and doc.revision_id != expected_revision_id:
            raise RunError("REVISION_CONFLICT", "The article changed; review the current revision before DEV delivery.")
        check_document(doc, inputs)
        ready = status(root)
        if ready["status"] != "review_ready":
            raise RunError("ARTICLE_NOT_REVIEWED", "Resolve article review blockers before explicit draft delivery.", 4)
        errors = media_errors(root, doc, public=True)
        if errors:
            raise RunError("MEDIA_UNRESOLVED", "; ".join(errors), 4)
        key = os.environ.get("PATCHPITCH_DEV_API_KEY", "")
        if not key:
            raise RunError("DEV_KEY_MISSING", "Set PATCHPITCH_DEV_API_KEY only for explicit delivery.", 5)
        article = payload(doc, inputs)
        content_hash = digest(article)
        editorial_hash = digest({"metadata": doc.metadata.model_dump(), "body": article["body_markdown"]})
        path = root / "receipts/dev.json"
        previous = read_json(path) if path.exists() else None
        if existing_id is not None and (type(existing_id) is not int or existing_id <= 0):
            raise RunError("INVALID_ARTICLE_ID", "Article ID must be positive.")
        uncertain = previous and previous["status"] in {"sending", "delivery_unknown"}
        if uncertain and existing_id is None:
            raise RunError("DEV_OUTCOME_UNKNOWN", "Reconcile the uncertain write with its existing article ID; another blind POST is blocked.", 5)
        identity = existing_id or (previous or {}).get("article_id")
        if preflight:
            from .editorial_media import used_assets
            checks = []
            for asset in doc.assets:
                if asset.id in used_assets(doc):
                    check = public_fetch(asset.public_url, method="HEAD", limit=0)
                    checks.append({"asset_id": asset.id, "url": check["url"], "checked_at": now()})
            write_json(root / "receipts/media-preflight.json", {"revision_id": doc.revision_id, "checks": checks})
        if identity:
            remote = owned_article(identity, key)
            if existing_id is not None:
                if not previous or not matches_submitted(remote, previous["article"]):
                    raise RunError("DEV_RECONCILIATION_MISMATCH", "This owned draft differs from the uncertain submitted payload.", 5)
            else:
                seen = observable(remote, previous["article"])
                seen_hash = digest(seen)
                expected = previous.get("remote_sha256")
                if seen_hash != expected and (not expected_remote_hash or seen_hash != expected_remote_hash):
                    write_json(root / "receipts/remote-conflict.json", {"remote": seen, "remote_sha256": seen_hash,
                        "article_id": identity, "local_revision_id": doc.revision_id})
                    raise RunError("REMOTE_DRAFT_CHANGED", "DEV draft changed remotely. Inspect its diff, then explicitly use its remote hash or import the edits.", 5)
                if previous.get("content_sha256") == content_hash and seen_hash == expected:
                    return previous
        receipt = {"status": "sending", "article_id": identity, "article": article, "content_sha256": content_hash,
            "editorial_hash": editorial_hash, "revision_id": doc.revision_id, "recorded_at": now()}
        write_json(path, receipt)
        try:
            response = request_api("PUT" if identity else "POST", f"/articles/{identity}" if identity else "/articles", {"article": article}, key)
            if not isinstance(response, dict) or type(response.get("id")) is not int or (identity and response["id"] != identity):
                raise RunError("DEV_OUTCOME_UNKNOWN", "DEV did not return the expected draft identity.", 5)
            if response.get("published_at") or response.get("published") is True:
                raise RunError("DEV_OUTCOME_UNKNOWN", "DEV returned an unexpected publication state; inspect it manually.", 5)
            receipt["article_id"] = response["id"]
            # Confirm the written draft through the authenticated owned-article endpoint.
            verified = owned_article(response["id"], key)
            if not matches_submitted(verified, article):
                raise RunError("DEV_OUTCOME_UNKNOWN", "DEV's saved draft differs from the submitted content.", 5)
            receipt.update(status="remote_draft", remote_sha256=digest(observable(verified, article)),
                url=response.get("url"), remote_preview_reviewed=False)
        except RunError as exc:
            receipt["status"] = "delivery_failed" if exc.code == "DEV_REQUEST_REJECTED" else "delivery_unknown"
            write_json(path, receipt)
            raise
        write_json(path, receipt)
        return receipt


def review_preview(work, expected_revision_id):
    """Explicit operator attestation after viewing DEV, distinct from HTTP delivery."""
    root, manifest, doc, inputs = load(work)
    if doc.revision_id != expected_revision_id:
        raise RunError("REVISION_CONFLICT", "Review the current article revision first.")
    observed = inspect(root)
    path = root / "receipts/dev.json"
    with FileLock(root / ".editorial.lock"):
        _, _, current, current_inputs = load(root)
        receipt = read_json(path)
        current_hash = digest({"metadata": current.metadata.model_dump(), "body": body_markdown(current, current_inputs, True)})
        if (current.revision_id != expected_revision_id or receipt.get("editorial_hash") != current_hash or
                receipt.get("remote_sha256") != observed["remote_sha256"]):
            raise RunError("REMOTE_DRAFT_CHANGED", "Local or remote content changed since the inspected draft.", 5)
        receipt.update(remote_preview_reviewed=True, preview_reviewed_revision=current.revision_id, preview_reviewed_at=now())
        write_json(path, receipt)
        return {"status": "remote_preview_reviewed", "article_id": receipt["article_id"], "revision_id": current.revision_id}
