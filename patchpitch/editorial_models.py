"""Versioned editorial contracts. Text is preserved, never stripped on save."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .jobs import VoiceConfig


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


ID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")]
Text = Annotated[str, StringConstraints(max_length=3000)]
Hash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class Source(Model):
    kind: Literal["reviewed_fact_pack", "campaign_run"]
    path: str = Field(min_length=1, max_length=2000)
    target: str | None = None
    import_current_article: bool = False

    @model_validator(mode="after")
    def scope(self):
        if self.kind == "reviewed_fact_pack" and (self.target or self.import_current_article):
            raise ValueError("Only a campaign target can import its current article.")
        if self.kind == "campaign_run" and not self.target:
            raise ValueError("A campaign source needs a target ID.")
        return self


class Config(Model):
    schema_version: Literal["patchpitch.editorial-job/v1"]
    campaign_id: ID
    source: Source
    language: Literal["en", "ru"] = "en"
    writing_goal: Literal["release", "development"] = "development"
    narrator: Literal["first_person_singular", "team", "neutral"] = "first_person_singular"
    angle: str = Field(default="A concrete problem, observed result and useful example.", max_length=1000)
    voice: VoiceConfig | None = None
    x_voice: VoiceConfig | None = None
    style: Literal["warm", "clear", "lively"] | None = None
    max_model_requests: int = Field(default=32, ge=1, le=100)
    accept_valid_candidates: bool = False
    hashtag_catalog: str | None = None
    x_angles: list[Annotated[str, StringConstraints(min_length=1, max_length=300)]] = Field(
        default_factory=lambda: ["Useful result", "Concrete decision", "Practical example"], min_length=3, max_length=3)
    media_manifest: str | None = None

    @model_validator(mode="after")
    def voice_choice(self):
        if (self.voice is None) == (self.style is None):
            raise ValueError("Choose an explicit Quillgrain voice or an explicit preset.")
        if len(set(self.x_angles)) != 3:
            raise ValueError("Choose three distinct announcement angles.")
        return self


class PlanSection(Model):
    id: ID
    heading: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=1000)
    source_ids: list[ID] = Field(min_length=1, max_length=15)
    conditions: list[str] = Field(default_factory=list, max_length=15)
    code_refs: list[str] = Field(default_factory=list, max_length=15)
    media_refs: list[ID] = Field(default_factory=list, max_length=30)
    word_target: int = Field(default=160, ge=30, le=800)


class Outline(Model):
    title: str = Field(min_length=1, max_length=120)
    thesis: str = Field(min_length=1, max_length=1000)
    audience: str = Field(min_length=1, max_length=180)
    reader_outcome: str = Field(min_length=1, max_length=1000)
    angle: str = Field(min_length=1, max_length=1000)
    sections: list[PlanSection] = Field(min_length=1, max_length=12)
    omissions: dict[ID, Annotated[str, StringConstraints(min_length=1, max_length=1000)]] = Field(default_factory=dict)


class Block(Model):
    id: ID
    kind: Literal["paragraph", "list", "code", "media"]
    text: Text = ""
    items: list[Annotated[str, StringConstraints(min_length=1, max_length=3000)]] = Field(default_factory=list, max_length=30)
    source_ids: list[ID] = Field(default_factory=list, max_length=15)
    snippet_id: str = Field(default="", max_length=100)
    asset_id: str = Field(default="", max_length=80)
    editorial_context: bool = False

    @model_validator(mode="after")
    def content(self):
        expected = {"paragraph": bool(self.text.strip()), "list": bool(self.items),
                    "code": bool(self.snippet_id), "media": bool(self.asset_id)}
        if not expected[self.kind]:
            raise ValueError("A block must contain its declared content.")
        if ((self.kind != "paragraph" and self.text) or (self.kind != "list" and self.items)
                or (self.kind != "code" and self.snippet_id) or (self.kind != "media" and self.asset_id)):
            raise ValueError("A block may only contain fields for its kind.")
        if self.kind in {"paragraph", "list"} and not self.source_ids and not self.editorial_context:
            raise ValueError("Prose needs sources or an explicit editorial-context classification.")
        if self.editorial_context and (self.source_ids or self.kind != "paragraph"):
            raise ValueError("Editorial transitions are paragraphs, never factual citations.")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("Block sources must be unique.")
        return self


class Section(Model):
    id: ID
    heading: str = Field(min_length=1, max_length=120)
    blocks: list[Block] = Field(default_factory=list, max_length=96)
    locked: bool = False
    reviewed: bool = False


class Metadata(Model):
    title: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=300)
    tags: list[Annotated[str, StringConstraints(pattern=r"^[a-z0-9]{1,30}$")]] = Field(default_factory=list, max_length=4)
    cover_asset_id: str | None = None
    ai_disclosure_level: Literal["no_ai", "some_ai", "fully_autonomous"] = "fully_autonomous"

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("DEV tags must be unique.")
        return self


class Asset(Model):
    id: ID
    kind: Literal["image", "gif", "video", "subtitle"]
    path: str
    sha256: Hash
    size: int = Field(ge=1)
    mime: str
    alt: str = Field(default="", max_length=1000)
    decorative: bool = False
    caption: str = Field(default="", max_length=1000)
    provenance: str = Field(min_length=1, max_length=2000)
    public_url: str | None = None
    poster_id: str | None = None
    subtitle_id: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    audio_present: bool | None = None
    width: int | None = Field(default=None, ge=1, le=32768)
    height: int | None = Field(default=None, ge=1, le=32768)


class Document(Model):
    schema_version: Literal["patchpitch.editorial-document/v1"] = "patchpitch.editorial-document/v1"
    document_id: ID
    revision_id: str = ""
    parent_revision_id: str | None = None
    source_sha256: Hash
    voice_id: str | None = None
    catalog_id: str | None = None
    narrator: Literal["first_person_singular", "team", "neutral"] = "first_person_singular"
    language: Literal["en", "ru"] = "en"
    metadata: Metadata = Field(default_factory=Metadata)
    outline: Outline | None = None
    outline_reviewed: bool = False
    sources_reviewed: bool = False
    article_reviewed: bool = False
    sections: list[Section] = Field(default_factory=list, max_length=12)
    assets: list[Asset] = Field(default_factory=list, max_length=30)
    used_section_ids: list[ID] = Field(default_factory=list, max_length=10000)
    used_block_ids: list[ID] = Field(default_factory=list, max_length=20000)


class Mutation(Model):
    operation_id: ID
    expected_revision_id: str = Field(min_length=1, max_length=80)
    operations: list[dict] = Field(min_length=1, max_length=100)


class SectionResponse(Model):
    blocks: list[Block] = Field(min_length=1, max_length=32)


class ProseParagraph(Model):
    text: Annotated[str, StringConstraints(min_length=1, max_length=3000)]
    source_ids: list[ID] = Field(min_length=1, max_length=15)


class ProseResponse(Model):
    paragraphs: list[ProseParagraph] = Field(min_length=1, max_length=32)


class ImportResponse(Model):
    sections: list[Section] = Field(min_length=1, max_length=12)


class XIdea(Model):
    topic: str = Field(min_length=1, max_length=500)
    source_ids: list[ID] = Field(min_length=1, max_length=15)
    text: str = Field(min_length=1, max_length=500)


class XResponse(Model):
    posts: list[XIdea] = Field(min_length=3, max_length=3)


class XSingleResponse(Model):
    posts: list[XIdea] = Field(min_length=1, max_length=1)
