"""Validate explicit local save files. No server storage or model calls."""
import json
import hashlib
import math
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .models import Draft, PitchInput, PostDraft, Product, SocialInput, SourceContext, SourceReference
from .provenance import source_snapshot
from .validation import blocks


class FileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Text = Annotated[str, StringConstraints(max_length=100_000)]
SourceID = Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]
RecordID = Annotated[str, StringConstraints(pattern=r"^A[0-9]{2,6}$")]
FORMATS = {"devlog", "community", "short", "x_single", "x_thread"}


class Profile(FileModel):
    kind: Literal["patchpitch_profile"]
    schema_version: Literal[1]
    product: Product
    audience: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    cta_text: Annotated[str, StringConstraints(max_length=300)] = ""


class Form(FileModel):
    product: Annotated[str, StringConstraints(max_length=80)]
    description: Annotated[str, StringConstraints(max_length=400)]
    audience: Annotated[str, StringConstraints(max_length=180)]
    release: Annotated[str, StringConstraints(max_length=80)]
    voice: Annotated[str, StringConstraints(max_length=1200)]
    cta: Annotated[str, StringConstraints(max_length=300)]
    changes: Annotated[str, StringConstraints(max_length=6200)]
    media_note: Annotated[str, StringConstraints(max_length=500)]
    format: Literal["devlog", "community", "short", "x_single", "x_thread"]
    style: Literal["warm", "clear", "lively"]
    intent: Literal["show_result", "build_story", "release", "ask_question"]
    post_count: int = Field(ge=3, le=7)
    auto_tags: bool
    writing_goal: Literal["release", "development"]


class PreparedChange(FileModel):
    id: SourceID
    text: Annotated[str, StringConstraints(min_length=1, max_length=6000)]
    include: bool
    reason: Annotated[str, StringConstraints(max_length=600)] = ""


class PreparedSources(FileModel):
    product: Product
    audience: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    release_label: Annotated[str, StringConstraints(max_length=80)] = ""
    voice_reference: Annotated[str, StringConstraints(max_length=1200)] = ""
    cta_text: Annotated[str, StringConstraints(max_length=300)] = ""
    changes: list[PreparedChange] = Field(max_length=15)
    source_references: list[SourceReference] = Field(max_length=15)
    pack_id: Annotated[str, StringConstraints(max_length=80)] = ""
    pack_version: Annotated[str, StringConstraints(max_length=40)] = ""
    pack_sha256: Annotated[str, StringConstraints(pattern=r"^(?:[0-9a-f]{64})?$")] = ""
    review_required: bool = True
    source_context: SourceContext | None = None


class SavedPost(FileModel):
    id: Annotated[str, StringConstraints(pattern=r"^P0[1-7]$")]
    text: Annotated[str, StringConstraints(max_length=2200)]
    source_ids: list[SourceID] = Field(min_length=1, max_length=15)
    length: dict[str, Any] | None = None
    media_note: Annotated[str, StringConstraints(max_length=500)] = ""
    edited: bool = False
    local_record_id: RecordID | None = None


def validate_request(value):
    return (SocialInput if value.get("format", "").startswith("x_") else PitchInput).model_validate(value)


def validate_data(data):
    """Check every field consumed by the renderer, retaining the original JSON."""
    fmt = data["presentation"]["format"]
    if fmt not in FORMATS:
        raise ValueError("Unknown saved draft format.")
    request = validate_request(data["input_snapshot"])
    if request.format != fmt:
        raise ValueError("Draft format and its original input differ.")
    context = data["context"]
    if context["product"] != request.product.name or context["release_label"] != request.release_label:
        raise ValueError("Draft context and its original input differ.")
    expected_context = request.source_context.model_dump() if request.source_context else None
    if context.get("source_context") != expected_context:
        raise ValueError("Draft Git provenance differs from the original input.")
    for key, default in (("pack_id", ""), ("pack_version", ""), ("pack_sha256", ""), ("context_overrides", []), ("writing_goal", "release")):
        if context.get(key, default) != getattr(request, key):
            raise ValueError("Draft provenance differs from its original input.")
    datetime.fromisoformat(context["generated_at"].replace("Z", "+00:00"))
    if data.get("body_markdown") is not None and not isinstance(data["body_markdown"], str):
        raise ValueError("Invalid original body Markdown.")
    if data.get("media_note") is not None and (not isinstance(data["media_note"], str) or len(data["media_note"]) > 500):
        raise ValueError("Invalid media note.")
    for key in ("omitted_source_ids", "current_warnings", "regeneration_warnings"):
        value = data.get(key, [])
        if not isinstance(value, list) or len(value) > 200 or any(not isinstance(item, str) for item in value):
            raise ValueError("Invalid saved review metadata.")
    regenerations = data.get("regenerations", [])
    if not isinstance(regenerations, list) or len(regenerations) > 200:
        raise ValueError("Invalid rewrite history.")
    for attempt in regenerations:
        if not isinstance(attempt, dict) or not isinstance(attempt.get("warnings"), list) or any(not isinstance(w, str) for w in attempt["warnings"]):
            raise ValueError("Invalid rewrite warnings.")
    for key in ("format_label", "style_label"):
        if not isinstance(data["presentation"][key], str):
            raise ValueError("Invalid draft presentation.")
    limit = data["presentation"].get("limit")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("Invalid draft length limit.")
    elapsed = data["meta"]["elapsed_seconds"]
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid saved draft timing.")
    if any(not isinstance(w, str) or len(w) > 4000 for w in data["warnings"]):
        raise ValueError("Invalid saved draft warnings.")
    if not isinstance(data["warnings"], list) or len(data["warnings"]) > 100:
        raise ValueError("Too many warnings.")
    sources = data["sources"]
    expected = {c.id: c.text for c in request.changes if c.include}
    if sources != expected:
        raise ValueError("Saved source text differs from the original input.")
    if fmt.startswith("x_"):
        posts = [SavedPost.model_validate(p) for p in data["draft"]["posts"]]
        if not 1 <= len(posts) <= 7:
            raise ValueError("Invalid original post count.")
    else:
        (Draft if fmt == "devlog" else PostDraft).model_validate(data["draft"])
        if not isinstance(data["markdown"], str) or len(data["markdown"]) > 100_000:
            raise ValueError("Invalid original Markdown.")
    for item in data["source_map"]:
        if not isinstance(item["block"], str) or not set(item["source_ids"]) <= set(sources):
            raise ValueError("Invalid saved source map.")
    if "source_snapshot" in data:
        if data["source_snapshot"] != source_snapshot(request):
            raise ValueError("Source snapshot differs from its original input.")
        if len(data["source_snapshot"]) > 15:
            raise ValueError("Invalid source snapshot.")
        for item in data["source_snapshot"]:
            SourceReference.model_validate({k: item[k] for k in ("api_id", "stable_id", "source_url", "source_ref")})
            if type(item["include"]) is not bool or not isinstance(item["text"], str) or len(item["text"]) > 6000:
                raise ValueError("Invalid source snapshot.")
    elif fmt.startswith("x_"):
        raise ValueError("X drafts need their source snapshot.")
    if data.get("local_record_id") is not None and not isinstance(data["local_record_id"], str):
        raise ValueError("Invalid record identity.")


class SavedDraft(FileModel):
    data: dict[str, Any]
    markdown: Text
    tags: list[Annotated[str, StringConstraints(pattern=r"^#[A-Za-z][A-Za-z0-9]{0,39}$")]] = Field(max_length=3)
    edited: bool
    editing: bool
    posts: list[SavedPost] = Field(max_length=7)

    @model_validator(mode="after")
    def renderable(self):
        try:
            validate_data(self.data)
            social = self.data["presentation"]["format"].startswith("x_")
            ids = [p.id for p in self.posts]
            if len(ids) != len(set(ids)) or bool(self.posts) != social:
                raise ValueError("Invalid current post list.")
            if social and set(ids) != {p["id"] for p in self.data["draft"]["posts"]}:
                raise ValueError("Current posts must match the original thread identities.")
            if any(not set(p.source_ids) <= set(self.data["sources"]) for p in self.posts):
                raise ValueError("Current post cites an unknown source.")
            if social:
                expected_map = [{"block": p.id, "source_ids": p.source_ids} for p in self.posts]
            else:
                original = (Draft if self.data["presentation"]["format"] == "devlog" else PostDraft).model_validate(self.data["draft"])
                expected_map = [{"block": label, "source_ids": block.source_ids} for label, block in blocks(original)]
            used = {source for item in expected_map for source in item["source_ids"]}
            if self.data["source_map"] != expected_map or self.data.get("omitted_source_ids", []) != sorted(set(self.data["sources"]) - used):
                raise ValueError("Saved source usage does not match the current draft.")
        except (KeyError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError("Incomplete saved draft.") from exc
        return self


class Record(FileModel):
    schema_version: Literal[1]
    id: RecordID
    recorded_at: Annotated[str, StringConstraints(max_length=60)]
    status: Literal["failed", "accepted"]
    client_elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    input_snapshot: dict[str, Any]
    response: dict[str, Any] | None
    error: dict[str, Any] | None
    evidence: dict[str, Any] | None

    @model_validator(mode="after")
    def valid_attempt(self):
        if self.status == "accepted":
            validate_request(self.input_snapshot)
        else:
            # A 422 request is still valuable original evidence. Check the fields
            # used by the record UI without requiring the rejected input to pass
            # generation validation or silently normalizing its original text.
            product = self.input_snapshot.get("product")
            if (not isinstance(product, dict)
                    or not isinstance(product.get("name"), str)
                    or not isinstance(self.input_snapshot.get("release_label"), str)
                    or self.input_snapshot.get("format") not in FORMATS):
                raise ValueError("Invalid failed-attempt display fields.")
        datetime.fromisoformat(self.recorded_at.replace("Z", "+00:00"))
        if self.status == "accepted" and self.response is None:
            raise ValueError("An accepted attempt needs its original response.")
        if self.status == "failed" and (not self.error or not isinstance(self.error.get("message"), str)):
            raise ValueError("A failed attempt needs its error.")
        return self


class GitControls(FileModel):
    git_repo: Annotated[str, StringConstraints(max_length=1000)] = Field(default="", alias="git-repo")
    git_mode: Literal["recent", "range", "published"] = Field(default="recent", alias="git-mode")
    git_count: Annotated[str, StringConstraints(pattern=r"^[0-9]{0,3}$")] = Field(default="10", alias="git-count")
    git_base: Annotated[str, StringConstraints(max_length=200)] = Field(default="", alias="git-base")
    git_head: Annotated[str, StringConstraints(max_length=200)] = Field(default="HEAD", alias="git-head")
    git_path: Annotated[str, StringConstraints(max_length=300)] = Field(default="", alias="git-path")


class PublicationMarker(FileModel):
    head: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    url: Annotated[str, StringConstraints(max_length=500)]
    published_at: Annotated[str, StringConstraints(max_length=60)]

    @model_validator(mode="after")
    def valid_url(self):
        SourceReference(api_id="C01", stable_id="publication", source_url=self.url)
        datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
        return self


class GitFile(FileModel):
    path: Annotated[str, StringConstraints(max_length=300)]
    eligible: bool
    reason: Annotated[str, StringConstraints(max_length=200)]
    added: Annotated[str, StringConstraints(pattern=r"^(?:-|[0-9]+)$")]
    removed: Annotated[str, StringConstraints(pattern=r"^(?:-|[0-9]+)$")]


class GitCommit(FileModel):
    sha: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    subject: Annotated[str, StringConstraints(max_length=2000)]


class GitInspection(FileModel):
    repository: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    repository_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    base: Annotated[str, StringConstraints(pattern=r"^(?:[0-9a-f]{40})?$")]
    head: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    branch: Annotated[str, StringConstraints(max_length=200)]
    commit_count: int = Field(ge=1, le=50)
    commits: list[GitCommit] = Field(min_length=1, max_length=50)
    worktree_dirty: bool
    files: list[GitFile] = Field(max_length=200)
    path_filter: Annotated[str, StringConstraints(max_length=300)]
    status: Literal["committed"]
    note: Annotated[str, StringConstraints(max_length=500)]


class GitEvidence(FileModel):
    id: Annotated[str, StringConstraints(pattern=r"^D[0-9]{2}$")]
    path: Annotated[str, StringConstraints(max_length=300)]
    diff: Annotated[str, StringConstraints(max_length=6200)]


class GitPreview(FileModel):
    source_context: SourceContext
    evidence: list[GitEvidence] = Field(min_length=1, max_length=12)
    preview_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ReviewedCandidate(FileModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=800)]
    current_text: Annotated[str, StringConstraints(max_length=800)]
    include: bool
    evidence_ids: list[Annotated[str, StringConstraints(pattern=r"^D[0-9]{2}$")]] = Field(min_length=1, max_length=4)
    kind: Literal["implemented", "fix", "refactor", "uncertain"]


class GitReview(FileModel):
    inspection: GitInspection | None
    preview: GitPreview | None
    facts: list[ReviewedCandidate] | None = Field(max_length=15)
    record: dict[str, Any] | None
    selected_files: list[Annotated[str, StringConstraints(max_length=300)]] = Field(max_length=12)

    @model_validator(mode="after")
    def consistent(self):
        if not self.inspection:
            if self.preview or self.facts or self.selected_files:
                raise ValueError("An unfinished Git review needs its inspected range.")
            return self
        files = {f.path for f in self.inspection.files if f.eligible}
        if len(self.selected_files) != len(set(self.selected_files)) or not set(self.selected_files) <= files:
            raise ValueError("Invalid saved Git file selection.")
        if not self.preview:
            if self.facts:
                raise ValueError("Fact candidates need their diff snapshot.")
            return self
        context = self.preview.source_context
        if (context.base, context.head, context.repository_id) != (self.inspection.base, self.inspection.head, self.inspection.repository_id):
            raise ValueError("Git review range mismatch.")
        if [e.path for e in self.preview.evidence] != self.selected_files:
            raise ValueError("Git evidence and selected files differ.")
        ids = [e.id for e in self.preview.evidence]
        if ids != [f"D{i:02}" for i in range(1, len(ids)+1)]:
            raise ValueError("Invalid diff identities.")
        evidence = [e.model_dump() for e in self.preview.evidence]
        if sum(len(e.diff.encode("utf-8")) for e in self.preview.evidence) > 24_000:
            raise ValueError("Saved diff budget exceeded.")
        fingerprint = {"base": context.base, "head": context.head, "evidence": evidence}
        expected = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if expected != self.preview.preview_sha256:
            raise ValueError("Saved diff fingerprint mismatch.")
        for fact in self.facts or []:
            if len(fact.evidence_ids) != len(set(fact.evidence_ids)) or not set(fact.evidence_ids) <= set(ids):
                raise ValueError("Fact candidate cites an absent diff.")
        return self


class Session(FileModel):
    kind: Literal["patchpitch_session"]
    schema_version: Literal[1]
    form: Form
    changes: list[PreparedChange] = Field(max_length=15)
    preview_text: Annotated[str, StringConstraints(max_length=6200)] | None
    pack_context: PreparedSources | None
    drafts: list[SavedDraft] = Field(max_length=100)
    active_key: Annotated[str, StringConstraints(max_length=400)] | None
    records: list[Record] = Field(max_length=200)
    record_choice: RecordID | None
    git_controls: GitControls = Field(default_factory=GitControls)
    publication_markers: dict[Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")], PublicationMarker] = Field(default_factory=dict)
    git_record: dict[str, Any] | None = None
    git_review: GitReview | None = None

    @model_validator(mode="after")
    def consistent(self):
        ids = [c.id for c in self.changes]
        if ids != [f"C{i:02}" for i in range(1, len(ids) + 1)] or sum(len(c.text) for c in self.changes) > 6000:
            raise ValueError("Invalid saved selection.")
        if self.pack_context:
            refs = [r.api_id for r in self.pack_context.source_references]
            stable = [r.stable_id for r in self.pack_context.source_references]
            if refs != ids or len(stable) != len(set(stable)):
                raise ValueError("Source references must match the current selection.")
        keys = [json.dumps([d.data["context"]["product"], d.data["context"]["release_label"], d.data["presentation"]["format"]], ensure_ascii=False, separators=(",", ":")) for d in self.drafts]
        if len(keys) != len(set(keys)) or (self.active_key is not None and self.active_key not in keys):
            raise ValueError("Invalid active draft or duplicate saved drafts.")
        records = {r.id for r in self.records}
        if len(records) != len(self.records) or (self.record_choice is not None and self.record_choice not in records):
            raise ValueError("Invalid saved generation record selection.")
        for draft in self.drafts:
            linked = [draft.data.get("local_record_id"), *(p.local_record_id for p in draft.posts)]
            if any(item is not None and item not in records for item in linked):
                raise ValueError("A draft points to an absent generation record.")
        return self


def validate_file(data):
    try:
        # Bound depth and reject non-JSON numeric values before rehydrating state.
        def visit(value, depth=0):
            if depth > 35:
                raise ValueError("Save file is nested too deeply.")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Save file contains a non-finite number.")
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"__proto__", "prototype", "constructor"}:
                        raise ValueError("Unsupported save-file key.")
                    visit(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    visit(child, depth + 1)
        visit(data)
        model = Profile if data.get("kind") == "patchpitch_profile" else Session
        model.model_validate(data)
        return data  # Preserve exact Unicode, whitespace, raw responses and edits.
    except (KeyError, TypeError, AttributeError, RecursionError, OverflowError) as exc:
        raise ValueError("Invalid or incomplete save file.") from exc
