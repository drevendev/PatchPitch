"""Declarative unattended jobs. Paths are relative to the job, never the cwd."""
import tomllib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator, ValidationError

from .models import StrictModel
from .run_store import RunError, read_json

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,79}$")]
FileName = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class Execution(StrictModel):
    max_model_requests: int = Field(default=32, ge=1, le=100)
    inference_attempts_per_step: Literal[1] = 1
    continue_other_targets_on_error: bool = True


class FactSource(StrictModel):
    kind: Literal["reviewed_fact_pack"]
    path: FileName


class GitSource(StrictModel):
    kind: Literal["git_range"]
    repository: FileName
    base: str
    head: str = "HEAD"
    files: list[FileName] = Field(min_length=1, max_length=12)
    candidate_selection: Literal["all_valid_candidates", "selection_file"]
    selection_file: FileName | None = None

    @model_validator(mode="after")
    def selected(self):
        if (self.candidate_selection == "selection_file") != bool(self.selection_file):
            raise ValueError("selection_file is required only for selection_file mode.")
        if len(self.files) != len(set(self.files)):
            raise ValueError("Git files must be unique.")
        return self


class VoiceConfig(StrictModel):
    model_config = {**StrictModel.model_config, "populate_by_name": True, "serialize_by_alias": True}
    provider: Literal["quillgrain"] = "quillgrain"
    mode: Literal["bundle", "local_pack"]
    path: FileName
    register_name: Annotated[str, StringConstraints(min_length=1, max_length=100)] = Field(default="maker_announcement", alias="register")
    bindings: dict[str, FileName] = Field(default_factory=dict, max_length=30)
    overlays: list[FileName] = Field(default_factory=list, max_length=10)
    tags: list[Annotated[str, StringConstraints(max_length=100)]] = Field(default_factory=list, max_length=40)
    example_pool: str | None = None
    max_chars: int = Field(default=8000, ge=1, le=24000)
    expected_build: str | None = None


class Target(StrictModel):
    id: Identifier
    channel: Literal["telegram", "x", "dev", "github"]
    format: Literal["telegram", "x_single", "x_thread", "dev_article", "github_release_notes"]
    language: Literal["en", "ru"] = "en"
    voice: Identifier | None = None
    style: Literal["warm", "clear", "lively"] | None = None
    post_count: int = Field(default=5, ge=3, le=7)
    intent: Literal["show_result", "build_story", "release", "ask_question"] = "show_result"
    hashtag_catalog: FileName | None = None
    hashtag_policy: Literal["x-six-v1"] | None = None

    @model_validator(mode="after")
    def compatible(self):
        allowed = {"telegram": {"telegram"}, "x": {"x_single", "x_thread"},
                   "dev": {"dev_article"}, "github": {"github_release_notes"}}
        if self.format not in allowed[self.channel]:
            raise ValueError("Channel and format differ.")
        if self.voice and self.style:
            raise ValueError("Select a voice or preset, not both.")
        if self.channel == "x" and (not self.hashtag_catalog or not self.hashtag_policy):
            raise ValueError("X requires a catalog and x-six-v1 policy.")
        if self.channel != "x" and (self.hashtag_catalog or self.hashtag_policy):
            raise ValueError("X hashtag policy belongs to X targets.")
        return self


class Job(StrictModel):
    schema_version: Literal["patchpitch.job/v1"]
    campaign_id: Identifier
    product_profile: FileName
    writing_goal: Literal["release", "development"] = "development"
    source: Annotated[FactSource | GitSource, Field(discriminator="kind")]
    execution: Execution = Field(default_factory=Execution)
    voices: dict[Identifier, VoiceConfig] = Field(default_factory=dict, max_length=20)
    targets: list[Target] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def references(self):
        if len({t.id for t in self.targets}) != len(self.targets):
            raise ValueError("Target IDs must be unique.")
        if any(t.voice and t.voice not in self.voices for t in self.targets):
            raise ValueError("Unknown voice reference.")
        if self.source.kind == "git_range" and self.writing_goal != "development":
            raise ValueError("Git alone establishes development progress, not a release.")
        return self


def load_config(path):
    path = Path(path).resolve()
    if path.suffix.lower() == ".json":
        return read_json(path, 1_000_000)
    if path.suffix.lower() != ".toml":
        raise RunError("CONFIG_FORMAT", "Use a .json or .toml configuration.")
    try:
        with path.open("rb") as handle:
            raw = handle.read(1_000_001)
        if len(raw) > 1_000_000:
            raise RunError("FILE_TOO_LARGE", "Configuration exceeds 1 MB.")
        return tomllib.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise RunError("INVALID_CONFIG", "Cannot read valid, bounded UTF-8 TOML.") from exc


def validate_model(model, value):
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        fields = [".".join(map(str, e["loc"])) + ": " + e["type"] for e in exc.errors(include_input=False)]
        raise RunError("INVALID_INPUT", "; ".join(fields)) from exc


def local_path(base, value):
    return (Path(base) / value).resolve()
