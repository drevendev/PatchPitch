"""Explicit Markdown candidates and private folder bundles, without inference."""
import json
import re
import uuid
from pathlib import Path

from .editorial import load, inside, check_document, apply, operation
from .editorial_models import Section, Block
from .campaign_export import text_file
from .run_store import RunError, FileLock, digest, write_json, write_bytes
from .campaigns import now


def import_markdown(work, path, source_map=None, operation_id=None, expected_revision_id=None):
    root, manifest, doc, inputs = load(work)
    if not doc.outline:
        raise RunError("OUTLINE_REQUIRED", "Create a plan before importing section text.", 4)
    text = text_file(path)
    if text.lstrip().startswith("---"):
        raise RunError("MARKDOWN_FRONT_MATTER", "Move front matter into explicit metadata edits before importing; publication flags are never executed.", 4)
    if len(text) > 32000:
        raise RunError("ARTICLE_LENGTH", "Imported Markdown exceeds 32000 characters.", 4)
    if text.startswith("# "):
        text = text.split("\n", 1)[1].lstrip("\n") if "\n" in text else ""
    identity = operation_id or "import-" + uuid.uuid4().hex
    request = {"markdown": text, "source_map": source_map, "expected_revision_id": expected_revision_id}
    old = operation(manifest, identity, request)
    if old:
        return old["result"]
    if expected_revision_id and expected_revision_id != doc.revision_id:
        raise RunError("REVISION_CONFLICT", "The article changed before import.")
    chunks = re.split(r"(?m)^## (.+)\n", text.replace("\r\n", "\n"))
    if chunks[0].strip() or len(chunks) < 3:
        raise RunError("MARKDOWN_STRUCTURE", "Use the accepted section headings (## Heading) so the import has explicit boundaries.", 4)
    headings = {s.heading: s for s in doc.sections}
    if len(headings) != len(doc.sections):
        raise RunError("MARKDOWN_STRUCTURE", "Duplicate headings need manual section edits instead of ambiguous Markdown import.", 4)
    seen, changes, unresolved = set(), [], []
    source_map = source_map or {}
    for index in range(1, len(chunks), 2):
        heading, body = chunks[index], chunks[index + 1]
        if heading not in headings or heading in seen:
            raise RunError("MARKDOWN_STRUCTURE", "Imported headings must match unique accepted sections.", 4)
        seen.add(heading)
        current = headings[heading]
        refs = source_map.get(current.id, [])
        blocks = []
        pieces = re.split(r"(```[^\n]*\n.*?```)", body, flags=re.S)
        for piece in pieces:
            if not piece.strip():
                continue
            if piece.startswith("```"):
                matches = [k for k, v in inputs["snippets"].items() if v["text"] == piece]
                if len(matches) != 1:
                    unresolved.append("UNSOURCED_CODE:" + current.id)
                    continue
                blocks.append(Block(id="B" + digest(identity)[:12] + "-" + str(index) + "-" + str(len(blocks)),
                    kind="code", snippet_id=matches[0], source_ids=[inputs["snippets"][matches[0]]["source_id"]]))
            else:
                for paragraph in re.split(r"\n\s*\n", piece.strip("\n")):
                    if not paragraph.strip():
                        continue
                    bid = "B" + digest(identity)[:12] + "-" + str(index) + "-" + str(len(blocks))
                    image = re.fullmatch(r"!\[.*?\]\(<?([^)>]+)>?\)", paragraph)
                    if image:
                        asset = next((a for a in doc.assets if image[1] in {a.path, a.public_url}), None)
                        if asset:
                            blocks.append(Block(id=bid, kind="media", asset_id=asset.id))
                        else:
                            unresolved.append("MEDIA_UNRESOLVED:" + current.id)
                    elif all(line.startswith("- ") for line in paragraph.splitlines()):
                        if not refs:
                            unresolved.append("CITATIONS_REQUIRED:" + current.id)
                            continue
                        blocks.append(Block(id=bid, kind="list", items=[line[2:] for line in paragraph.splitlines()], source_ids=refs))
                    else:
                        if not refs:
                            unresolved.append("CITATIONS_REQUIRED:" + current.id)
                        blocks.append(Block(id=bid, kind="paragraph", text=paragraph, source_ids=refs, editorial_context=not refs))
        changes.append({"type": "section", "value": Section(id=current.id, heading=current.heading, blocks=blocks).model_dump()})
    if seen != set(headings):
        raise RunError("MARKDOWN_STRUCTURE", "Import all accepted sections or edit one section directly.", 4)
    if not unresolved:
        from .editorial import mutate
        copy_doc = doc.model_copy(deep=True)
        for change in changes:
            mutate(root, copy_doc, inputs, change)
        check_document(copy_doc, inputs)
    status = "needs_review" if unresolved else "candidate"
    result = {"status": status, "candidate": identity, "revision_id": doc.revision_id, "unresolved": sorted(set(unresolved))}
    with FileLock(root / ".editorial.lock"):
        _, current_manifest, current, _ = load(root)
        if current.revision_id != doc.revision_id:
            raise RunError("REVISION_CONFLICT", "The article changed during import.")
        write_json(root / f"attempts/{identity}.json", {"id": identity, "kind": "markdown_import", "status": status,
            "base_revision_id": doc.revision_id, "markdown": text, "candidate": changes,
            "unresolved": sorted(set(unresolved)), "recorded_at": now()})
        current_manifest["operations"][identity] = {"request_sha256": digest(request), "result": result}
        write_json(root / "manifest.json", current_manifest)
    return result


def bundle(work, out):
    root, manifest, doc, inputs = load(work)
    destination = Path(out).resolve()
    if destination == root or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise RunError("BUNDLE_PATH", "Choose a separate empty folder for the private workspace bundle.")
    if destination.exists() and any(destination.iterdir()):
        raise RunError("OUTPUT_NOT_EMPTY", "Choose an empty private bundle folder.")
    with FileLock(root / ".editorial.lock"):
        for prefix in ("inputs", "voices", "revisions", "attempts", "receipts", "media"):
            for path in (root / prefix).rglob("*") if (root / prefix).exists() else []:
                if path.is_file():
                    name = path.relative_to(root).as_posix()
                    source = inside(root, name)
                    target = inside(destination, name, exists=False)
                    with source.open("rb") as handle:
                        raw = handle.read(200 * 1024 ** 2 + 1)
                    if len(raw) > 200 * 1024 ** 2:
                        raise RunError("BUNDLE_BUDGET", "A private bundle file exceeds its budget.")
                    write_bytes(target, raw)
        write_json(destination / "manifest.json", manifest)
    return {"status": "bundled", "revision_id": doc.revision_id, "private": True,
            "warnings": ["This folder includes private sources, voices, original responses and draft receipts."], "artifacts": {"workspace": str(destination)}}
