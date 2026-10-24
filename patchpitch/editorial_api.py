"""Thin local studio transport; the same editorial domain serves CLI and UI."""
import json
import secrets
import tempfile
from collections import OrderedDict
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from . import editorial as domain, editorial_generation as writing, editorial_render as rendering
from .run_store import RunError, write_json, read_json

PREVIEWS = OrderedDict()


def create_from_form(data):
    with tempfile.TemporaryDirectory(prefix="patchpitch-editorial-input-") as temporary:
        base = Path(temporary)
        write_json(base / "facts.json", data["facts"])
        config = {"schema_version": "patchpitch.editorial-job/v1", "campaign_id": data.get("campaign_id", "my-article"),
            "source": {"kind": "reviewed_fact_pack", "path": "facts.json"}, "language": data.get("language", "en"),
            "narrator": data.get("narrator", "first_person_singular"), "writing_goal": data.get("writing_goal", "development")}
        if data.get("voice_bundle"):
            write_json(base / "voice.json", data["voice_bundle"])
            config["voice"] = {"provider": "quillgrain", "mode": "bundle", "path": "voice.json",
                "register": data["voice_bundle"]["context"]["register"]}
        else:
            config["style"] = data.get("style", "clear")
        if data.get("x_voice_bundle"):
            write_json(base / "x-voice.json", data["x_voice_bundle"])
            config["x_voice"] = {"provider": "quillgrain", "mode": "bundle", "path": "x-voice.json",
                "register": data["x_voice_bundle"]["context"]["register"]}
        if data.get("catalog"):
            write_json(base / "catalog.json", data["catalog"])
            config["hashtag_catalog"] = "catalog.json"
        write_json(base / "editorial.json", config)
        return domain.initialize(base / "editorial.json", data["work"])


def dispatch(data):
    if not isinstance(data.get("work"), str) or not 1 <= len(data["work"]) <= 2000:
        raise RunError("ARGUMENT_ERROR", "Choose a bounded local article folder path.")
    for field in ("verify", "dry_run", "reaffirm", "preflight", "retry_failed"):
        if field in data and type(data[field]) is not bool:
            raise RunError("ARGUMENT_ERROR", "Operation flags must be booleans.")
    action, work = data["action"], data["work"]
    if action == "init":
        return domain.initialize(data["config"], work) if data.get("config") else create_from_form(data)
    if action == "status":
        return domain.status(work, include_document=True)
    if action == "apply":
        return domain.apply(work, data["mutation"])
    if action in {"outline", "revise", "x"}:
        return writing.propose(work, "section" if action == "revise" else action, data.get("operation_id"), data.get("section_id"),
            data.get("instruction", ""), data.get("expected_revision_id"), data.get("dry_run", False), data.get("retry_failed", False))
    if action == "draft":
        return writing.draft(work, data.get("operation_id"), data.get("dry_run", False), data.get("retry_failed", False))
    if action == "accept":
        return writing.accept(work, data["candidate"], data["expected_revision_id"], data.get("operation_id"))
    if action in {"recover", "reject"}:
        return getattr(writing, action)(work, data["candidate"])
    if action == "edit-x":
        from .editorial_x import edit_series
        return edit_series(work, data.get("post_id"), data.get("text"), data.get("reaffirm", False),
            data.get("operation_id"), data.get("expected_revision_id"), data.get("source_ids"))
    if action == "import-markdown":
        from .editorial_import import import_markdown
        return import_markdown(work, data["path"], data.get("source_map"), data.get("operation_id"), data.get("expected_revision_id"))
    if action == "bundle":
        from .editorial_import import bundle
        return bundle(work, data["out"])
    if action == "validate":
        return domain.validate(work)
    if action in {"preview", "export"}:
        root, manifest, doc, _ = domain.load(work)
        if data.get("expected_revision_id") and data["expected_revision_id"] != doc.revision_id:
            raise RunError("REVISION_CONFLICT", "The article changed; reopen it before preview/export.")
        out = data.get("out") or str(root / "exports" / doc.revision_id / rendering.export_identity(manifest, doc)[:16])
        value = rendering.export(work, out)
        token = secrets.token_urlsafe(24)
        PREVIEWS[token] = Path(out).resolve()
        while len(PREVIEWS) > 32:
            PREVIEWS.popitem(last=False)
        value["preview_url"] = f"/editorial-preview/{token}/preview.html"
        return value
    if action == "deliver":
        from .editorial_dev import deliver
        return deliver(work, data.get("existing_id"), data.get("remote_hash"), data.get("preflight", False))
    if action == "remote":
        from .editorial_dev import inspect
        return inspect(work)
    if action == "review-dev-preview":
        from .editorial_dev import review_preview
        return review_preview(work, data["expected_revision_id"])
    if action == "bind-url":
        from .editorial_x import bind_url
        return bind_url(work, data["url"], data.get("verify", False), data.get("operation_id"))
    if action == "x-export":
        from .editorial_x import export_series
        root, manifest, doc, _ = domain.load(work)
        return export_series(root, manifest, doc)
    raise RunError("ARGUMENT_ERROR", "Unknown editorial action.")


def register(app):
    @app.get("/editorial")
    def editorial_page():
        return FileResponse(Path(__file__).parent / "static/editorial.html")

    @app.post("/api/editorial")
    async def editorial_action(data: dict):
        try:
            if len(json.dumps(data)) > 1_000_000:
                raise RunError("INPUT_TOO_LARGE", "Editorial requests must fit within 1 MB.")
            return await run_in_threadpool(dispatch, data)
        except RunError as exc:
            return JSONResponse({"error": exc.as_dict()}, status_code=409 if exc.code in {"REVISION_CONFLICT", "RUN_BUSY"} else 422)
        except (KeyError, ValueError, TypeError, OSError):
            return JSONResponse({"error": {"code": "EDITORIAL_INPUT", "message": "Check required fields, local paths and JSON files. Existing work is preserved."}}, status_code=422)

    @app.get("/editorial-preview/{token}/{name:path}")
    def editorial_preview(token: str, name: str):
        root = PREVIEWS.get(token)
        if root is None:
            raise HTTPException(404, "Preview expired; generate it again.")
        try:
            exported = read_json(root / "export.json")
            if name not in exported["files"]:
                raise HTTPException(404, "Not a preview asset.")
            path = domain.inside(root, name)
        except RunError:
            raise HTTPException(404, "Preview asset unavailable.")
        return FileResponse(path)
