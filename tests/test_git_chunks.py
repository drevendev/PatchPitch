import copy
import json

import pytest

from patchpitch import git_chunks


@pytest.mark.parametrize("text", [
    "".join(f"+value_{i} = {i}\n" for i in range(1800)),
    "@@ -1 +1 @@\n-"+"old"*4000+"\n+"+"Привет 🦀 e\u0301"*1300,
    "+"+'"\\\t'*7000+"\n",
], ids=["many-lines", "unicode-long-lines", "escaped"])
def test_chunks_preserve_every_byte_and_fit_serialized_requests(text):
    evidence = git_chunks.evidence_for("src/код.py", text, 1)
    assert "".join(e["diff"] for e in evidence) == text
    assert len(evidence) > 1
    position = 0
    for index, e in enumerate(evidence, 1):
        assert e["part"] == index and e["parts"] == len(evidence)
        assert e["start_byte"] == position
        position += len(e["diff"].encode())
        assert e["end_byte"] == position
        assert len(e["diff"].encode()) <= git_chunks.CHUNK_BYTES
    plan = git_chunks.batch_plan(evidence)
    assert [i for b in plan["batches"] for i in b["evidence_ids"]] == [e["id"] for e in evidence]
    assert all(b["bytes"] <= git_chunks.BATCH_BYTES for b in plan["batches"])
    for batch in plan["batches"]:
        items = [e for e in evidence if e["id"] in batch["evidence_ids"]]
        assert batch["bytes"] == len(json.dumps(items,ensure_ascii=False).encode())
    git_chunks.validate_chunks(evidence, ["src/код.py"], plan)


def test_chunks_keep_hunk_orientation_without_inventing_source_lines():
    text = "diff --git a/a.py b/a.py\n@@ -1,1000 +1,1000 @@ function_name\n"+"+some line\n"*1000
    evidence = git_chunks.evidence_for("a.py", text, 1)
    assert evidence[1]["hunk_header"] == "@@ -1,1000 +1,1000 @@"
    assert "".join(e["diff"] for e in evidence) == text
    assert all("function_name" not in e["hunk_header"] for e in evidence)


def test_split_added_line_cannot_invent_a_hunk_header():
    text = "diff --git a/a.py b/a.py\n@@ -1 +1 @@\n+" + "x"*5999 + "@@ -99 +99 @@" + "x"*14000
    evidence = git_chunks.evidence_for("a.py", text, 1)
    assert "".join(e["diff"] for e in evidence) == text
    assert all(e["hunk_header"] in {"", "@@ -1 +1 @@"} for e in evidence)


@pytest.mark.parametrize("damage", ["offset", "part", "missing", "plan", "order"])
def test_saved_chunk_layout_cannot_silently_omit_or_repeat_data(damage):
    evidence = git_chunks.evidence_for("a.py", "+"+"x"*22000, 1)
    plan = git_chunks.batch_plan(evidence)
    if damage == "offset": evidence[1]["start_byte"] += 1
    if damage == "part": evidence[1]["part"] = 1
    if damage == "missing": evidence.pop(1)
    if damage == "plan": plan["batches"][0]["evidence_ids"].pop()
    if damage == "order": evidence.reverse()
    with pytest.raises(ValueError): git_chunks.validate_chunks(evidence, ["a.py"], plan)


def test_fingerprint_binds_plan_and_repository_and_preserves_legacy_hash():
    evidence = [{"id":"D01", "path":"a.py", "diff":"+line\n"}]
    plan = git_chunks.batch_plan(evidence)
    first = git_chunks.preview_hash("a"*40, "b"*40, evidence, plan, "c"*64)
    assert first != git_chunks.preview_hash("a"*40, "b"*40, evidence, plan, "d"*64)
    changed = copy.deepcopy(plan); changed["batches"][0]["bytes"] += 1
    assert first != git_chunks.preview_hash("a"*40, "b"*40, evidence, changed, "c"*64)
    import hashlib
    old = hashlib.sha256(json.dumps({"base":"a"*40,"head":"b"*40,"evidence":evidence}, sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    assert git_chunks.preview_hash("a"*40,"b"*40,evidence) == old
