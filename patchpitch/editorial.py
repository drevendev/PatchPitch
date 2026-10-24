"""Editorial workspace: immutable revisions, compare-and-swap and shared operations."""
import copy
import hashlib
import re
from pathlib import Path

from pydantic import ValidationError

from .editorial_models import Config, Document, Mutation, Outline, Section, Metadata, Asset
from .run_store import FileLock, RunError, digest, read_json, write_json
from .campaigns import now


def parse(model, value):
    try:
        return model.model_validate(value)
    except (ValidationError, ValueError, TypeError) as exc:
        raise RunError("EDITORIAL_SCHEMA", f"Invalid {model.__name__}; check its schema and field limits.") from exc


def inside(root, name, exists=True):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root or (exists and not path.is_file()):
        raise RunError("WORKSPACE_PATH", "Expected a regular file inside the workspace.")
    return path


def load(work):
    root = Path(work).resolve()
    manifest = read_json(inside(root, "manifest.json"))
    if manifest.get("schema_version") != "patchpitch.editorial-work/v1":
        raise RunError("EDITORIAL_VERSION", "Unsupported editorial workspace version.")
    revision = manifest.get("revision_id", "")
    if not re.fullmatch(r"R[0-9a-f]{64}", revision):
        raise RunError("EDITORIAL_IDENTITY", "Invalid revision identity.")
    doc = parse(Document, read_json(inside(root, f"revisions/{revision}.json")))
    value = doc.model_dump()
    value["revision_id"] = ""
    if doc.revision_id != revision or revision != "R" + digest(value):
        raise RunError("EDITORIAL_IDENTITY", "The accepted document was modified outside an operation.")
    inputs = read_json(inside(root, "inputs/snapshot.json"))
    if digest(inputs) != manifest.get("input_sha256") or digest(inputs["sources"]) != doc.source_sha256:
        raise RunError("EDITORIAL_IDENTITY", "The immutable editorial inputs were changed.")
    return root, manifest, doc, inputs


def commit(root, manifest, doc):
    doc.revision_id = ""
    doc.revision_id = "R" + digest(doc.model_dump())
    target = inside(root, f"revisions/{doc.revision_id}.json", exists=False)
    if target.exists() and read_json(target) != doc.model_dump():
        raise RunError("EDITORIAL_IDENTITY", "Refusing to replace an immutable revision.")
    write_json(target, doc.model_dump())
    manifest["revision_id"] = doc.revision_id
    manifest["updated_at"] = now()
    write_json(inside(root, "manifest.json", exists=False), manifest)
    return doc


def inputs_from_config(config, base):
    from .jobs import local_path
    from .fact_packs import FactPack, prepare_pack
    from .campaign_export import load_run, current_result
    from .voice import prepare_voice
    source_path = local_path(base, config.source.path)
    imported = None
    if config.source.kind == "reviewed_fact_pack":
        pack = parse(FactPack, read_json(source_path))
        sources = prepare_pack(pack)
        for change, fact in zip(sources["changes"], pack.facts):
            change["include"] = fact.include and (fact.kind == "released" or
                (config.writing_goal == "development" and fact.kind == "internal"))
        sources["review_status"] = "reviewed_fact_pack"
    else:
        path, snap, manifest = load_run(source_path)
        targets = [t for t in snap["job"]["targets"] if t["id"] == config.source.target]
        if len(targets) != 1:
            raise RunError("TARGET_NOT_READY", "Select a known campaign target.")
        sources = read_json(path / "sources.json")
        if config.source.import_current_article:
            if targets[0]["format"] != "dev_article" or manifest["targets"][targets[0]["id"]]["status"] != "succeeded":
                raise RunError("TARGET_NOT_READY", "Select a completed DEV article for import.")
            _, imported = current_result(path, snap, targets[0])
    selected = [c for c in sources["changes"] if c["include"]]
    if not selected:
        raise RunError("NO_SELECTED_FACTS", "Select at least one eligible source fact.")
    bundle = prepare_voice(config.voice, base, language=config.language, format="dev_article") if config.voice else None
    x_bundle = prepare_voice(config.x_voice, base, language=config.language, format="x_single") if config.x_voice else None
    catalog = None
    if config.hashtag_catalog:
        from .hashtags import Catalog
        catalog = parse(Catalog, read_json(local_path(base, config.hashtag_catalog))).model_dump()
    snippets = {}
    for change in selected:
        for index, code in enumerate(re.findall(r"```[^\n]*\n.*?```", change["text"], re.S), 1):
            snippets[f"{change['id']}-code-{index}"] = {"source_id": change["id"], "text": code,
                "sha256": hashlib.sha256(code.encode()).hexdigest()}
    return {"config": config.model_dump(), "sources": sources, "snippets": snippets,
            "voice_bundle": bundle, "x_voice_bundle": x_bundle, "catalog": catalog}, imported


def initialize(config_path, out):
    from .jobs import load_config
    config_path = Path(config_path).resolve()
    config = parse(Config, load_config(config_path))
    root = Path(out).resolve()
    if root.exists() and any(root.iterdir()):
        raise RunError("OUTPUT_NOT_EMPTY", "Choose an empty editorial workspace.")
    inputs, imported = inputs_from_config(config, config_path.parent)
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(root / ".editorial.lock"):
        if any(p.name != ".editorial.lock" for p in root.iterdir()):
            raise RunError("OUTPUT_NOT_EMPTY", "Another operation already initialized this folder.")
        write_json(root / "inputs/snapshot.json", inputs)
        voice_id = digest(inputs["voice_bundle"]) if inputs["voice_bundle"] else None
        if voice_id:
            write_json(root / f"voices/{voice_id}.json", inputs["voice_bundle"])
        doc = Document(document_id=config.campaign_id, source_sha256=digest(inputs["sources"]),
                       language=config.language, narrator=config.narrator, voice_id=voice_id)
        manifest = {"schema_version": "patchpitch.editorial-work/v1", "input_sha256": digest(inputs),
            "created_at": now(), "operations": {}, "request_count": 0, "x_series": None, "public_url": None}
        commit(root, manifest, doc)
        if imported:
            # Unknown Markdown boundaries/citations remain an unaccepted import candidate.
            write_json(root / "attempts/imported-article.json", {"id": "imported-article", "kind": "markdown_import",
                "status": "needs_review", "base_revision_id": doc.revision_id, "markdown": imported["draft"]["text"],
                "metadata": {k: imported["draft"][k] for k in ("title", "description", "tags")}})
    if config.media_manifest:
        from .jobs import local_path
        media = read_json(local_path(config_path.parent, config.media_manifest))
        operations = []
        for item in media["assets"]:
            operations.append({"type": "import_media", **item,
                "path": str(local_path(config_path.parent, item["path"]))})
        apply(root, {"operation_id": "initial-media", "expected_revision_id": doc.revision_id, "operations": operations})
    return status(root)


def facts(inputs):
    return {c["id"]: c["text"] for c in inputs["sources"]["changes"] if c["include"]}


def check_outline(outline, inputs, assets):
    selected = set(facts(inputs))
    ids = [s.id for s in outline.sections]
    cited = {sid for s in outline.sections for sid in s.source_ids}
    if len(ids) != len(set(ids)) or cited - selected or set(outline.omissions) - selected:
        raise RunError("OUTLINE_SOURCES", "Plan IDs and citations must be unique and selected.", 4)
    if cited & set(outline.omissions) or cited | set(outline.omissions) != selected:
        raise RunError("OUTLINE_COVERAGE", "Place every selected fact or explicitly explain its omission.", 4)
    for section in outline.sections:
        if len(section.source_ids) != len(set(section.source_ids)):
            raise RunError("OUTLINE_SOURCES", "Section source IDs must be unique.", 4)
        if set(section.code_refs) - set(inputs["snippets"]) or set(section.media_refs) - assets:
            raise RunError("OUTLINE_REFERENCES", "Plan code/media references must exist.", 4)
        if any(inputs["snippets"][sid]["source_id"] not in section.source_ids for sid in section.code_refs):
            raise RunError("OUTLINE_REFERENCES", "Code must belong to this section's selected sources.", 4)


def check_document(doc, inputs):
    assets = {a.id: a for a in doc.assets}
    if len(assets) != len(doc.assets) or len({s.id for s in doc.sections}) != len(doc.sections):
        raise RunError("DUPLICATE_ID", "Document entity IDs must be unique.", 4)
    if doc.outline:
        check_outline(doc.outline, inputs, set(assets))
        if [s.id for s in doc.sections] != [s.id for s in doc.outline.sections]:
            raise RunError("SECTION_PLAN", "Document sections must follow the accepted plan.", 4)
    elif doc.sections:
        raise RunError("OUTLINE_REQUIRED", "Create a plan before sections.", 4)
    ids = [b.id for s in doc.sections for b in s.blocks]
    if len(ids) > 96 or len(set(ids)) != len(ids):
        raise RunError("BLOCK_BUDGET", "Use at most 96 unique blocks.", 4)
    for section in doc.sections:
        plan = next(s for s in doc.outline.sections if s.id == section.id)
        if "\n" in section.heading or "\r" in section.heading:
            raise RunError("HEADING_INVALID", "Headings must be single lines.", 4)
        for block in section.blocks:
            if not set(block.source_ids) <= set(plan.source_ids):
                raise RunError("SECTION_SOURCES", "A section cannot expand its allowed facts.", 4)
            if block.kind == "code" and (block.snippet_id not in plan.code_refs or
                    inputs["snippets"][block.snippet_id]["source_id"] not in block.source_ids):
                raise RunError("UNSOURCED_CODE", "Use a permitted exact source snippet.", 4)
            if block.kind == "media" and block.asset_id not in assets:
                raise RunError("MEDIA_MISSING", "A referenced media asset is missing.", 4)
            if block.kind in {"paragraph", "list"}:
                prose = block.text + " ".join(block.items)
                if "```" in prose or re.match(r"\s*---(?:\r?\n|$)", prose):
                    raise RunError("BLOCK_MARKUP", "Use code-reference blocks; front matter is not permitted.", 4)
                allowed = "\n".join(facts(inputs)[sid] for sid in block.source_ids)
                for command in re.findall(r"`((?:python |patchpitch |pip |qg )[^`\n]*)`", prose):
                    if command not in allowed:
                        raise RunError("UNSOURCED_CODE", "A command is absent from this block's cited sources.", 4)
                if any(p not in allowed for p in re.findall(r"\b\d+(?:\.\d+)?\s*%", prose)):
                    raise RunError("UNSOURCED_METRIC", "A percentage is absent from this block's cited sources.", 4)
    if doc.metadata.cover_asset_id and (doc.metadata.cover_asset_id not in assets or
            assets[doc.metadata.cover_asset_id].kind not in {"image", "gif"}):
        raise RunError("COVER_INVALID", "Cover must reference an imported image.", 4)
    for asset in doc.assets:
        from .editorial_media import validate_asset
        validate_asset(asset, assets)
    from .editorial_render import body_markdown
    if len(body_markdown(doc, inputs, public=False)) > 32000:
        raise RunError("ARTICLE_LENGTH", "The complete body exceeds 32000 characters.", 4)


def operation(manifest, opid, request):
    parse(Mutation, {"operation_id": opid, "expected_revision_id": "check", "operations": [{}]})
    previous = manifest["operations"].get(opid)
    if previous and previous["request_sha256"] != digest(request):
        raise RunError("OPERATION_CONFLICT", "This operation ID was already used for another request.")
    return previous


def apply(work, value):
    mutation = parse(Mutation, value)
    root = Path(work).resolve()
    with FileLock(root / ".editorial.lock"):
        root, manifest, doc, inputs = load(root)
        previous = operation(manifest, mutation.operation_id, value)
        if previous:
            return previous["result"]
        if mutation.expected_revision_id != doc.revision_id:
            raise RunError("REVISION_CONFLICT", "The document changed; review the current revision before applying.")
        original = doc.model_copy(deep=True)
        for item in mutation.operations:
            mutate(root, doc, inputs, item)
        check_document(doc, inputs)
        doc.parent_revision_id = original.revision_id
        # Review-only operations may certify the current content; content edits always invalidate it.
        before = original.model_dump(exclude={"revision_id", "parent_revision_id", "sources_reviewed", "outline_reviewed", "article_reviewed"})
        after = doc.model_dump(exclude={"revision_id", "parent_revision_id", "sources_reviewed", "outline_reviewed", "article_reviewed"})
        if before != after:
            doc.article_reviewed = False
        result = {"status": "accepted", "operation_id": mutation.operation_id}
        # Both commit and operation receipt are part of the one manifest switch.
        doc.revision_id = ""
        revision = "R" + digest(doc.model_dump())
        result["revision_id"] = revision
        manifest["operations"][mutation.operation_id] = {"request_sha256": digest(value), "result": result}
        commit(root, manifest, doc)
        return result


def mutate(root, doc, inputs, item):
    kind = item.get("type")
    allowed = {"outline": {"value"}, "section": {"value"}, "metadata": {"value"}, "review_sources": set(),
        "review_outline": set(), "review_section": {"section_id"}, "review_article": set(),
        "lock_section": {"section_id", "locked"}, "import_media": {"id", "path", "alt", "caption", "provenance", "decorative"},
        "asset": {"id", "value"}, "voice": {"config", "base"}, "rollback": {"revision_id"}, "narrator": {"value"}}
    if kind not in allowed or set(item) - ({"type"} | allowed[kind]):
        raise RunError("MUTATION_INVALID", "Unknown operation or operation fields.")
    required = {"import_media": {"id", "path", "provenance"}}.get(kind, allowed[kind])
    if not required <= set(item):
        raise RunError("MUTATION_INVALID", "This operation is missing required fields.")
    if kind == "outline":
        plan = parse(Outline, item["value"])
        check_outline(plan, inputs, {a.id for a in doc.assets})
        current = {s.id: s for s in doc.sections}
        if any(s.locked and s.id not in {p.id for p in plan.sections} for s in doc.sections):
            raise RunError("SECTION_LOCKED", "Unlock a section before removing it from the outline.")
        for p in plan.sections:
            if p.id in doc.used_section_ids and p.id not in current:
                raise RunError("REUSED_ID", "Deleted section IDs cannot be reused.")
        replacement = []
        for p in plan.sections:
            section = current.get(p.id, Section(id=p.id, heading=p.heading))
            prior = next((s for s in doc.outline.sections if s.id == p.id), None) if doc.outline else None
            if prior is None or prior.model_dump() != p.model_dump():
                if section.locked and section.heading != p.heading:
                    raise RunError("SECTION_LOCKED", "Unlock the section before changing its heading.")
                section.heading, section.reviewed = p.heading, False
            replacement.append(section)
            if p.id not in doc.used_section_ids:
                doc.used_section_ids.append(p.id)
        doc.outline, doc.sections, doc.outline_reviewed = plan, replacement, False
        if not doc.metadata.title:
            doc.metadata.title = plan.title
    elif kind == "section":
        section = parse(Section, item["value"])
        current = next((s for s in doc.sections if s.id == section.id), None)
        if current is None:
            raise RunError("SECTION_UNKNOWN", "Select a section in the accepted outline.")
        if current.locked:
            raise RunError("SECTION_LOCKED", "Unlock this section before replacing it.")
        current_ids = {b.id for b in current.blocks}
        for block in section.blocks:
            if block.id in doc.used_block_ids and block.id not in current_ids:
                raise RunError("REUSED_ID", "Deleted or other-section block IDs cannot be reused.")
            if block.id not in doc.used_block_ids:
                doc.used_block_ids.append(block.id)
        section.locked, section.reviewed = current.locked, False
        doc.sections = [section if s.id == section.id else s for s in doc.sections]
    elif kind == "metadata":
        doc.metadata = parse(Metadata, {**doc.metadata.model_dump(), **item["value"]})
    elif kind == "review_sources":
        doc.sources_reviewed = True
    elif kind == "review_outline":
        if not doc.outline:
            raise RunError("OUTLINE_REQUIRED", "Create the outline first.", 4)
        doc.outline_reviewed = True
    elif kind in {"lock_section", "review_section"}:
        section = next((s for s in doc.sections if s.id == item["section_id"]), None)
        if section is None:
            raise RunError("SECTION_UNKNOWN", "Select an existing section.")
        if kind == "review_section":
            if not section.blocks:
                raise RunError("SECTION_EMPTY", "Write the section before reviewing it.", 4)
            section.reviewed = True
        else:
            if type(item["locked"]) is not bool:
                raise RunError("MUTATION_INVALID", "locked must be boolean.")
            section.locked = item["locked"]
    elif kind == "review_article":
        if not doc.sources_reviewed or not doc.outline_reviewed or not doc.sections or any(not s.blocks for s in doc.sections):
            raise RunError("ARTICLE_NOT_REVIEWED", "Review sources, plan and complete all sections first.", 4)
        required = {sid for section in doc.outline.sections for sid in section.source_ids}
        used = {sid for section in doc.sections for block in section.blocks for sid in block.source_ids}
        if not required <= used:
            raise RunError("ARTICLE_SOURCE_COVERAGE", "The article has not cited every fact required by its approved outline.", 4)
        doc.article_reviewed = True
    elif kind == "import_media":
        from .editorial_media import import_asset
        if any(a.id == item["id"] for a in doc.assets):
            raise RunError("DUPLICATE_ID", "Choose a new media asset ID.")
        doc.assets.append(import_asset(root, item, doc.assets))
    elif kind == "asset":
        asset = next((a for a in doc.assets if a.id == item["id"]), None)
        if asset is None or set(item["value"]) - {"alt", "caption", "decorative", "public_url", "poster_id", "subtitle_id"}:
            raise RunError("MEDIA_INVALID", "Only existing media presentation/mappings can be changed.")
        doc.assets = [parse(Asset, {**a.model_dump(), **item["value"]}) if a.id == asset.id else a for a in doc.assets]
    elif kind == "voice":
        from .jobs import VoiceConfig
        from .voice import prepare_voice
        config = parse(VoiceConfig, item["config"])
        value = prepare_voice(config, Path(item["base"]), language=doc.language, format="dev_article")
        doc.voice_id = digest(value)
        write_json(root / f"voices/{doc.voice_id}.json", value)
    elif kind == "narrator":
        if item["value"] not in {"first_person_singular", "team", "neutral"}:
            raise RunError("MUTATION_INVALID", "Choose a supported narrator.")
        doc.narrator = item["value"]
    elif kind == "rollback":
        revision = item["revision_id"]
        if not re.fullmatch(r"R[0-9a-f]{64}", revision):
            raise RunError("EDITORIAL_IDENTITY", "Select a valid historical revision.")
        old = parse(Document, read_json(inside(root, f"revisions/{revision}.json")))
        old_identity = old.model_dump()
        old_identity["revision_id"] = ""
        if old.revision_id != revision or revision != "R" + digest(old_identity):
            raise RunError("EDITORIAL_IDENTITY", "The historical revision was changed outside an operation.")
        if old.document_id != doc.document_id or old.source_sha256 != doc.source_sha256:
            raise RunError("EDITORIAL_IDENTITY", "Rollback must use this document's history.")
        reserved_s, reserved_b = doc.used_section_ids[:], doc.used_block_ids[:]
        for key, value in old.model_dump().items():
            if key not in {"revision_id", "parent_revision_id", "used_section_ids", "used_block_ids"}:
                setattr(doc, key, getattr(old, key))
        doc.used_section_ids, doc.used_block_ids = reserved_s, reserved_b
        doc.article_reviewed = False


def status(work, include_document=False):
    root, manifest, doc, inputs = load(work)
    from .editorial_media import media_errors
    from .editorial_render import body_markdown
    errors = media_errors(root, doc, public=False)
    blockers = []
    if not doc.sources_reviewed:
        blockers.append("SOURCES_NOT_REVIEWED")
    if not doc.outline or not doc.outline_reviewed:
        blockers.append("OUTLINE_NOT_REVIEWED")
    if not doc.sections or any(not s.blocks for s in doc.sections):
        blockers.append("ARTICLE_INCOMPLETE")
    if not doc.article_reviewed:
        blockers.append("ARTICLE_NOT_REVIEWED")
    if not doc.metadata.title.strip() or not doc.metadata.description.strip():
        blockers.append("ARTICLE_METADATA_REQUIRED")
    public_errors = media_errors(root, doc, public=True)
    receipt_path = root / "receipts/dev.json"
    receipt = read_json(receipt_path) if receipt_path.exists() else None
    current_hash = digest({"metadata": doc.metadata.model_dump(), "body": body_markdown(doc, inputs, public=True)})
    series = manifest.get("x_series")
    if series:
        series = read_json(inside(root, f"attempts/{series}.json"))
    x_state = "not_generated" if not series else "stale" if series["article_sha256"] != article_hash(doc) else "awaiting_public_url"
    if series and x_state != "stale" and (manifest.get("public_url") or {}).get("verified"):
        x_state = "ready"
    value = {"status": "review_ready" if not blockers and not errors else "draft_ready" if doc.sections and all(s.blocks for s in doc.sections)
        else "outline_ready" if doc.outline else "sources_ready", "revision_id": doc.revision_id,
        "document_id": doc.document_id, "blockers": blockers + errors, "media_ready_for_dev": not public_errors,
        "media_blockers": public_errors, "request_count": manifest["request_count"],
        "dev_sync_state": "not_delivered" if not receipt else receipt["status"] if receipt.get("editorial_hash") == current_hash else "stale",
        "x_state": x_state, "public_url": manifest.get("public_url"),
        "artifacts": {"workspace": str(root)}, "attempts": []}
    if include_document:
        value["document"] = doc.model_dump()
        value["sources"] = inputs["sources"]
        value["attempts"] = [{k: a.get(k) for k in ("id", "kind", "status", "base_revision_id", "candidate", "error")}
            for p in sorted((root / "attempts").glob("*.json")) for a in [read_json(p)]]
    return value


def article_hash(doc):
    value = doc.model_dump(exclude={"revision_id", "parent_revision_id", "article_reviewed", "sources_reviewed",
        "outline_reviewed", "used_section_ids", "used_block_ids"})
    for section in value["sections"]:
        section.pop("reviewed", None)
        section.pop("locked", None)
    return digest(value)


def validate(work):
    root, manifest, doc, inputs = load(work)
    check_document(doc, inputs)
    return status(root)
