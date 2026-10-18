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


class PitchInput(StrictModel):
    product: Product
    audience: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    release_label: Annotated[str, StringConstraints(max_length=80)] = ""
    voice_reference: Annotated[str, StringConstraints(max_length=1200)] = ""
    changes: list[Change] = Field(min_length=1, max_length=15)
    cta_text: Annotated[str, StringConstraints(max_length=300)] = ""
    format: Literal["devlog", "community", "short"] = "devlog"
    style: Literal["warm", "clear", "lively"] = "warm"
    auto_tags: bool = False
    confirmed: bool

    @model_validator(mode="after")
    def check_changes(self):
        if not self.confirmed:
            raise ValueError("Confirm that the selected changes belong in this announcement.")
        if sum(len(c.text) for c in self.changes) > 6000:
            raise ValueError("Use at most 6,000 characters of change notes.")
        if [c.id for c in self.changes] != [f"C{i:02}" for i in range(1, len(self.changes) + 1)]:
            raise ValueError("Change IDs must be assigned in order, starting at C01.")
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
    highlights: list[Block] = Field(min_length=1, max_length=3)
    details: list[Block] = Field(default_factory=list, max_length=4)
    note: Block | None = None
    hashtags: list[Annotated[str, StringConstraints(pattern=r"^#[A-Za-z][A-Za-z0-9]{0,39}$")]] = Field(default_factory=list, max_length=3)


class PostDraft(StrictModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=2200)]
    source_ids: list[Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]] = Field(min_length=1, max_length=15)
    hashtags: list[Annotated[str, StringConstraints(pattern=r"^#[A-Za-z][A-Za-z0-9]{0,39}$")]] = Field(default_factory=list, max_length=3)


PITCH_SCHEMA = Draft.model_json_schema()
