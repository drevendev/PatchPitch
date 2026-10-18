from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


ShortText = Annotated[str, StringConstraints(min_length=1, max_length=400)]


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
    changes: list[Change] = Field(min_length=1, max_length=15)
    cta_text: Annotated[str, StringConstraints(max_length=300)] = ""
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
        return self


class PrepareInput(StrictModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=6200)]


class Block(StrictModel):
    text: ShortText
    source_ids: list[Annotated[str, StringConstraints(pattern=r"^C[0-9]{2}$")]] = Field(min_length=1, max_length=15)


class TitleBlock(Block):
    text: Annotated[str, StringConstraints(min_length=1, max_length=72)]


class Draft(StrictModel):
    title: TitleBlock
    intro: Block
    highlights: list[Block] = Field(min_length=1, max_length=3)
    note: Block | None = None


PITCH_SCHEMA = Draft.model_json_schema()
