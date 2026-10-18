import json
from pathlib import Path

import pytest


@pytest.fixture
def input_data():
    return json.loads((Path(__file__).resolve().parents[1] / "examples" / "pocket-orchard.json").read_text())


@pytest.fixture
def draft_data():
    return {"title": {"text": "Find your notes, keep your words", "source_ids": ["C01", "C02"]},
            "intro": {"text": "Find notes by title and export a notebook as Markdown.", "source_ids": ["C01", "C02"]},
            "highlights": [{"text": "Search notes by title.", "source_ids": ["C01"]}, {"text": "Export a notebook as Markdown.", "source_ids": ["C02"]}, {"text": "Saving no longer duplicates a note.", "source_ids": ["C03"]}], "note": None}
