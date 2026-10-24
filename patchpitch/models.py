from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


ShortText = Annotated[str, StringConstraints(max_length=1200)]


class Product(StrictModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    description: Annotated[str, StringConstraints(min_length=1, max_length=400)]


class Change(StrictModel):
    id: Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]
    text: Annotated[str, StringConstraints(min_length=1, max_length=6000)]
    include: bool


class SourceReference(StrictModel):
    api_id: Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]
    stable_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")]
    source_url: Annotated[str, StringConstraints(max_length=500)] = ""
    source_ref: Annotated[str, StringConstraints(max_length=2000)] = ""

    @model_validator(mode="after")
    def safe_url(self):
        from urllib.parse import urlsplit
        if self.source_url:
            parsed = urlsplit(self.source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Source URLs must be ordinary http(s) links without credentials.")
        return self


class SourceContext(StrictModel):
    kind: Literal["git"]
    repository: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    repository_id: Annotated[str, StringConstraints(pattern=r"^(?:[0-9a-f]{64})?$")] = ""
    base: Annotated[str, StringConstraints(pattern=r"^(?:[0-9a-f]{40})?$")]
    head: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    branch: Annotated[str, StringConstraints(max_length=200)] = ""
    commit_count: int = Field(ge=1, le=50)
    worktree_dirty: bool
    status: Literal["committed"] = "committed"
    omitted_files: list[Annotated[str, StringConstraints(max_length=500)]] = Field(default_factory=list, max_length=200)
    partial: bool = False


class PitchInput(StrictModel):
    product: Product
    audience: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    release_label: Annotated[str, StringConstraints(max_length=80)] = ""
    voice_reference: Annotated[str, StringConstraints(max_length=1200)] = ""
    changes: list[Change] = Field(min_length=1, max_length=15)
    cta_text: Annotated[str, StringConstraints(max_length=300)] = ""
    language: Literal["en", "ru"] = "en"
    voice_bundle: dict | None = None
    voice_register: Annotated[str, StringConstraints(min_length=1, max_length=100)] = "maker_announcement"
    tag_allowlist: list[Annotated[str, StringConstraints(pattern=r"^#[\w]{1,40}$")]] = Field(default_factory=list, max_length=5)
    format: Literal["devlog", "community", "short", "telegram"] = "devlog"
    style: Literal["warm", "clear", "lively", "voice"] = "warm"
    auto_tags: bool = False
    confirmed: bool
    source_references: list[SourceReference] = Field(default_factory=list, max_length=15)
    pack_id: Annotated[str, StringConstraints(max_length=80)] = ""
    pack_version: Annotated[str, StringConstraints(max_length=40)] = ""
    pack_sha256: Annotated[str, StringConstraints(pattern=r"^(?:[0-9a-f]{64})?$")] = ""
    context_overrides: list[Literal["product", "description", "audience", "release_label", "voice_reference", "cta_text"]] = Field(default_factory=list, max_length=6)
    source_context: SourceContext | None = None
    writing_goal: Literal["release", "development"] = "release"

    @model_validator(mode="after")
    def check_changes(self):
        if self.voice_bundle is not None:
            from .voice import validate_bundle
            validate_bundle(self.voice_bundle, language=self.language, format=self.format, register=self.voice_register)
            if self.style != "voice" or self.voice_reference:
                raise ValueError("Choose Quillgrain voice without a competing preset or prose sample.")
        elif self.style == "voice":
            raise ValueError("Load a Quillgrain voice export or choose a normal preset.")
        if not self.confirmed:
            raise ValueError("Confirm that the selected changes belong in this announcement.")
        if sum(len(c.text) for c in self.changes) > 6000:
            raise ValueError("Use at most 6,000 characters of change notes.")
        if [c.id for c in self.changes] != [f"C{i:02}" for i in range(1, len(self.changes) + 1)]:
            raise ValueError("Change IDs must be assigned in order, starting at C01.")
        refs = [r.api_id for r in self.source_references]
        stable = [r.stable_id for r in self.source_references]
        if refs and (refs != [c.id for c in self.changes] or len(stable) != len(set(stable))):
            raise ValueError("Source references must map every change, in order, to a unique stable ID.")
        if self.source_context and self.writing_goal != "development":
            raise ValueError("Git sources establish committed code, not a published release. Use Development progress.")
        if not any(c.include for c in self.changes):
            raise ValueError("Select at least one change.")
        if self.format == "short" and len(self.cta_text) > 180:
            raise ValueError("Shorten the call to action to 180 characters or choose a longer format.")
        return self


class PrepareInput(StrictModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=6200)]


class Block(StrictModel):
    text: ShortText
    source_ids: list[Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]] = Field(min_length=1, max_length=15)
    retained_facts: list[Annotated[str, StringConstraints(min_length=1, max_length=6000)]] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def has_content(self):
        if not self.text and not self.retained_facts:
            raise ValueError("A block needs prose or retained source sentences.")
        return self


class TitleBlock(Block):
    text: Annotated[str, StringConstraints(min_length=1, max_length=120)]


class Draft(StrictModel):
    title: TitleBlock
    intro: Block
    highlights: list[Block] = Field(min_length=0, max_length=3)
    details: list[Block] = Field(default_factory=list, max_length=4)
    note: Block | None = None
    hashtags: list[Annotated[str, StringConstraints(pattern=r"^#[\w]{1,40}$")]] = Field(default_factory=list, max_length=5)


    @model_validator(mode="after")
    def has_topics(self):
        if not self.highlights and self.note is None:
            raise ValueError("A Devlog needs a selected topic or an important note.")
        return self


class PostDraft(StrictModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    source_ids: list[Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]] = Field(min_length=1, max_length=15)
    hashtags: list[Annotated[str, StringConstraints(pattern=r"^#[\w]{1,40}$")]] = Field(default_factory=list, max_length=5)


PITCH_SCHEMA = Draft.model_json_schema()




class SocialPost(StrictModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    source_ids: list[Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]] = Field(min_length=1, max_length=15)


class ContextPost(SocialPost):
    id: Annotated[str, StringConstraints(pattern=r"^P0[1-7]$")]


class SocialDraft(StrictModel):
    posts: list[SocialPost] = Field(min_length=1, max_length=7)


class HashtagPostPlan(StrictModel):
    id: Annotated[str, StringConstraints(pattern=r"^P0[1-7]$")]
    topic: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    source_ids: list[Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]] = Field(min_length=1, max_length=15)
    hashtags: list[Annotated[str, StringConstraints(pattern=r"^#[\w]{1,40}$")]] = Field(min_length=6, max_length=6)


class SocialInput(PitchInput):
    format: Literal["x_single", "x_thread"] = "x_single"
    auto_tags: Literal[False] = False
    hashtag_policy: Literal["legacy", "x-six-v1"] = "legacy"
    hashtag_catalog: dict | None = None
    hashtag_plan: list[HashtagPostPlan] = Field(default_factory=list, max_length=7)
    intent: Literal["show_result", "build_story", "release", "ask_question"] = "show_result"
    post_count: int = Field(default=5, ge=3, le=7)
    operation: Literal["generate", "regenerate"] = "generate"
    target_post_id: Annotated[str, StringConstraints(pattern=r"^P0[1-7]$")] | None = None
    thread_context: list[ContextPost] = Field(default_factory=list, max_length=7)

    @model_validator(mode="after")
    def check_social(self):
        from .social_count import estimate
        if self.hashtag_policy == "x-six-v1":
            from .hashtags import Catalog, canonical
            if self.hashtag_catalog is None:
                raise ValueError("Load an evidence-backed X hashtag catalog.")
            catalog = Catalog.model_validate(self.hashtag_catalog)
            expected = 1 if self.format == "x_single" else self.post_count
            if self.hashtag_plan and ([p.id for p in self.hashtag_plan] != [f"P{i:02}" for i in range(1, expected + 1)]):
                raise ValueError("Hashtag plan must match the complete post plan.")
            for post in self.hashtag_plan:
                if not set(post.source_ids) <= {c.id for c in self.changes if c.include}:
                    raise ValueError("Tag plan cites an unselected fact.")
                if len({canonical(t) for t in post.hashtags}) != 6:
                    raise ValueError("Tag plan must contain six unique tags.")
        elif self.hashtag_plan or self.hashtag_catalog:
            raise ValueError("Legacy X requests cannot carry a six-tag plan.")
        if self.cta_text and estimate(self.cta_text)["characters"] + 3 > 280:
            raise ValueError("Shorten the call to action to leave room for the post.")
        ids = [p.id for p in self.thread_context]
        if len(ids) != len(set(ids)):
            raise ValueError("Thread post IDs must be unique.")
        if self.operation == "regenerate":
            expected = self.post_count if self.format == "x_thread" else 1
            if self.target_post_id not in ids or len(ids) != expected:
                raise ValueError("Regeneration needs the selected post and the complete current thread.")
            allowed = {c.id for c in self.changes if c.include}
            if any(not set(p.source_ids) <= allowed for p in self.thread_context):
                raise ValueError("Thread context cites an unknown or excluded fact.")
        elif self.thread_context or self.target_post_id:
            raise ValueError("Thread context is only used for an explicit single-post regeneration.")
        return self
