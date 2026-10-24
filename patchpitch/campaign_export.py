"""Validate the editable export files and restore a campaign in the studio."""
import copy
from pathlib import Path

from . import sessions
from .campaigns import now, summary
from .hashtags import validate_export_post
from .run_store import FileLock, RunError, digest, read_json, write_json


def text_file(path, limit=128_000):
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise RunError("FILE_TOO_LARGE", "Edited text exceeds its export budget.", 4)
        return raw.decode("utf-8").replace("\r\n", "\n").removesuffix("\n")
    except (OSError, UnicodeError) as exc:
        raise RunError("MISSING_EDITABLE_FILE", "A campaign's editable UTF-8 file is missing or unreadable.", 4) from exc


def load_run(path):
    path = Path(path).resolve()
    snap, manifest = read_json(path / "snapshot.json"), read_json(path / "manifest.json")
    if manifest.get("schema_version") != "patchpitch.run/v1" or digest(snap) != manifest.get("input_sha256"):
        raise RunError("RUN_INPUT_MISMATCH", "Invalid campaign manifest or input snapshot.")
    return path, snap, manifest


def current_result(path, snap, target):
    directory = path / "outputs" / target["id"]
    original = read_json(directory / "original.json")
    result = copy.deepcopy(original)
    fmt = target["format"]
    if fmt.startswith("x_"):
        from .models import SocialInput
        from .social_count import estimate
        request = SocialInput.model_validate(original["input_snapshot"])
        for post in result["draft"]["posts"]:
            post["text"] = text_file(directory / f"{post['id']}.txt", 20_000)
            validate_export_post(request, post)
            post["length"] = estimate(post["text"])
        result["markdown"] = "\n\n---\n\n".join(p["text"] for p in result["draft"]["posts"]) + "\n"
    elif fmt == "dev_article":
        metadata = read_json(directory / "article.json", 200_000)
        if (not isinstance(metadata.get("title"), str) or not 1 <= len(metadata["title"]) <= 120 or
                not isinstance(metadata.get("description", ""), str) or len(metadata.get("description", "")) > 300 or
                not isinstance(metadata.get("tags"), list) or len(metadata["tags"]) > 4 or
                any(not isinstance(t, str) or not t.isalnum() or not t.isascii() or len(t) > 30 for t in metadata["tags"])):
            raise RunError("INVALID_ARTICLE_METADATA", "Review the edited article title, description and up to four alphanumeric tags.", 4)
        body = text_file(directory / "article.md")
        result["draft"].update(title=metadata["title"], description=metadata.get("description", ""), tags=metadata["tags"], text=body)
        result["markdown"] = "# " + metadata["title"] + "\n\n" + body + "\n"
    else:
        result["markdown"] = text_file(directory / ("release-notes.md" if fmt == "github_release_notes" else "draft.md")) + "\n"
        if fmt == "telegram" and len(result["markdown"].removesuffix("\n")) > 4096:
            raise RunError("TELEGRAM_LENGTH_EXCEEDED", "The complete edited Telegram post exceeds 4096 codepoints.", 4)
    if not result["markdown"].strip():
        raise RunError("EMPTY_EXPORT", "The edited publication is empty.", 4)
    result["current_content_sha256"] = digest(result["markdown"])
    return original, result


def validate_run(path):
    path = Path(path).resolve()
    with FileLock(path / ".run.lock"):
        path, snap, manifest = load_run(path)
        if manifest["status"] == "no_changes":
            return summary(path, manifest), 0
        errors = []
        for target in snap["job"]["targets"]:
            if manifest["targets"][target["id"]]["status"] != "succeeded":
                errors.append({"target": target["id"], "code": "TARGET_NOT_READY", "message": "Target has no completed output."})
                continue
            directory = path / "outputs" / target["id"]
            try:
                _, result = current_result(path, snap, target)
                write_json(directory / "current.json", result)
                write_json(directory / "validation.json", {"status": "passed", "checked_at": now(),
                    "content_sha256": result["current_content_sha256"], "warnings": ["Manual meaning and source review is still required."]})
            except RunError as exc:
                errors.append({"target": target["id"], **exc.as_dict()})
                write_json(directory / "validation.json", {"status": "failed", "checked_at": now(), "error": exc.as_dict()})
        value = summary(path, manifest)
        value.update(status="validation_failed" if errors else "validated", errors=errors)
        return value, 4 if errors else 0


def export_session(path, destination):
    path = Path(path).resolve()
    with FileLock(path / ".run.lock"):
        path, snap, manifest = load_run(path)
        sources = read_json(path / "sources.json")
        drafts = []
        for target in snap["job"]["targets"]:
            if manifest["targets"][target["id"]]["status"] != "succeeded":
                continue
            original, current = current_result(path, snap, target)
            edited = current.get("markdown") != original.get("markdown")
            drafts.append({"data": original, "markdown": current["markdown"], "tags": [],
                           "edited": edited, "editing": edited and target["channel"] != "x",
                           "posts": current["draft"]["posts"] if target["channel"] == "x" else []})
        if not drafts:
            raise RunError("NO_COMPLETED_TARGETS", "There are no completed drafts to restore.", 4)
        request = drafts[0]["data"]["input_snapshot"]
        pack_context = {k: v for k, v in sources.items() if k not in {"writing_goal", "review_status", "context_overrides"}}
        # PreparedSources deliberately has a smaller contract than a generation.
        allowed = set(sessions.PreparedSources.model_fields)
        pack_context = {k: v for k, v in pack_context.items() if k in allowed}
        records = []
        for attempt_path in sorted((path / "attempts").glob("*.json")):
            attempt = read_json(attempt_path)
            if attempt["input_snapshot"].get("format") not in sessions.FORMATS or attempt["status"] not in {"accepted", "failed"}:
                continue
            records.append({"schema_version": 1, "id": attempt["id"], "recorded_at": attempt["recorded_at"],
                "status": attempt["status"], "client_elapsed_seconds": (attempt.get("response") or {}).get("meta", {}).get("elapsed_seconds", 0),
                "input_snapshot": attempt["input_snapshot"], "response": attempt["response"], "error": attempt["error"],
                "evidence": attempt.get("evidence")})
        form = {"product": request["product"]["name"], "description": request["product"]["description"],
                "audience": request["audience"], "release": request["release_label"], "voice": request["voice_reference"],
                "cta": request["cta_text"], "changes": "\n".join(c["text"] for c in sources["changes"]),
                "format": request["format"], "style": request["style"], "language": request["language"],
                "tag_allowlist": "", "media_note": "", "intent": request.get("intent", "show_result"),
                "post_count": request.get("post_count", 5), "auto_tags": False, "writing_goal": snap["job"]["writing_goal"]}
        saved = {"kind": "patchpitch_session", "schema_version": 1, "voice_bundle": request.get("voice_bundle"),
                 "x_catalog": next(iter(snap["catalogs"].values()), None),
                 "form": form, "changes": sources["changes"], "preview_text": form["changes"],
                 "pack_context": pack_context, "drafts": drafts, "active_key": sessions.draft_key(drafts[0]["data"]),
                 "records": records, "record_choice": records[-1]["id"] if records else None}
        checked = sessions.Session.model_validate(saved).model_dump(mode="json", by_alias=True)
        destination = Path(destination).resolve()
        if path in destination.parents and destination != path / "session.json":
            raise RunError("PROTECTED_RUN_FILE", "Inside the run, export only to session.json to preserve campaign files.")
        write_json(destination, checked)
