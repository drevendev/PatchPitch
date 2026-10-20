"""Versioned, explicitly reviewed local fact inputs. No URL/file fetching."""
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator
from .models import Product, SourceReference, StrictModel

PACKS = Path(__file__).parent / "fact_packs"
BUILTIN = ("patchpitch", "idle-fantasy-shop")


class Fact(StrictModel):
    id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")]
    text: Annotated[str, StringConstraints(min_length=1, max_length=6000)]
    include: bool
    kind: Literal["released", "internal", "planned", "unverified"]
    source_url: Annotated[str, StringConstraints(max_length=500)] = ""
    source_ref: Annotated[str, StringConstraints(max_length=600)] = ""
    limitations: Annotated[str, StringConstraints(max_length=600)] = ""

    @model_validator(mode="after")
    def provenance(self):
        SourceReference(api_id="C01", stable_id=self.id, source_url=self.source_url, source_ref=self.source_ref)
        if not self.source_url and not self.source_ref:
            raise ValueError("Each fact needs a source URL or a provenance reference.")
        return self


class FactPack(StrictModel):
    schema_version: Literal[1]
    id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{0,79}$")]
    version: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    product: Product
    audience: Annotated[str, StringConstraints(min_length=1, max_length=180)]
    release_label: Annotated[str, StringConstraints(max_length=80)] = ""
    voice_reference: Annotated[str, StringConstraints(max_length=1200)] = ""
    cta_text: Annotated[str, StringConstraints(max_length=300)] = ""
    facts: list[Fact] = Field(min_length=1, max_length=15)

    @model_validator(mode="after")
    def unique_and_bounded(self):
        if len({f.id for f in self.facts}) != len(self.facts):
            raise ValueError("Fact IDs must be unique.")
        if sum(len(f.text) + (len(f.limitations) + 1 if f.limitations else 0) for f in self.facts) > 6000:
            raise ValueError("Use at most 6,000 characters of facts and limitations.")
        return self


def prepare_pack(pack: FactPack):
    data = pack.model_dump()
    changes, references = [], []
    for i, fact in enumerate(pack.facts, 1):
        api_id = f"C{i:02}"
        changes.append({"id": api_id, "text": fact.text + (" " + fact.limitations if fact.limitations else ""),
                        "include": fact.include and fact.kind == "released",
                        "reason": "" if fact.kind == "released" else f"Marked {fact.kind}"})
        references.append({"api_id": api_id, "stable_id": fact.id, "source_url": fact.source_url, "source_ref": fact.source_ref})
    return {"product": data["product"], "audience": pack.audience, "release_label": pack.release_label,
            "voice_reference": pack.voice_reference, "cta_text": pack.cta_text, "changes": changes,
            "source_references": references, "pack_id": pack.id, "pack_version": pack.version,
            "pack_sha256": hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "review_required": True}


def load_pack(pack_id):
    if pack_id not in BUILTIN:
        raise KeyError(pack_id)
    return FactPack.model_validate_json((PACKS / f"{pack_id}.json").read_text(encoding="utf-8"))
