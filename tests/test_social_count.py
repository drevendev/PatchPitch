"""Authored URL regressions for #91, with explicit expected counts (not parity only).

Boundary categories were reviewed against twitter/twitter-text conformance/extract.yml;
these are our own fixtures, not a claim of complete upstream conformance.
"""
import json
from pathlib import Path

import pytest

from patchpitch.hashtags import validate_text
from patchpitch.run_store import RunError
from patchpitch.social_count import estimate, strip_urls, url_spans

CASES = json.loads((Path(__file__).parent / "fixtures/x-length-v2.json").read_text(encoding="utf-8"))
DEV_URL = CASES[2]["text"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_url_count_expected(case):
    expected = len(case["text"]) if case.get("raw") else case["characters"]
    assert estimate(case["text"]) == {"characters": expected, "limit": 280,
        "policy": "x-estimate-v2", "estimated": True, "over_limit": expected > 280, "requires_x_preview": True}
    if case.get("raw"):
        assert list(url_spans(case["text"])) == []


def test_only_url_fragments_are_removed_before_counting_hashtags():
    tags = "#DEVCommunity #DevTools #LocalAI #Ollama #OpenSource #Automation"
    text = f"Read ({DEV_URL}#inside) {tags}"
    assert strip_urls(text) == f"Read ( ) {tags}"
    validate_text(text)
    with pytest.raises(RunError, match="six unique"):
        validate_text(text.replace(" #Automation", ""))


def test_url_only_discounts_supported_host_labels():
    invalid = "https://" + "a" * 64 + ".example.com/path"
    assert estimate(invalid)["characters"] == len(invalid)


@pytest.mark.parametrize("size,over", [(256, False), (257, True)])
def test_exact_post_limit_includes_url_space_and_prose(size, over):
    text = "a" * size + " " + DEV_URL
    assert estimate(text)["characters"] == size + 24
    assert estimate(text)["over_limit"] is over
