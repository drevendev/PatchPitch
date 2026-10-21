import json
import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from patchpitch import generator, git_import
from patchpitch.app import app


def command(root, *args, input=None):
    return subprocess.check_output(["git", "-c", "core.hooksPath="+os.devnull, "-c", "commit.gpgsign=false",
        "-C", str(root), *args], input=input, stderr=subprocess.DEVNULL).decode().strip()


def commit(root, message):
    command(root, "add", "-A")
    command(root, "-c", "user.name=PatchPitch test", "-c", "user.email=patchpitch@example.invalid", "commit", "-qm", message)
    return command(root, "rev-parse", "HEAD")


@pytest.fixture
def git_repository(tmp_path):
    root = tmp_path/"project"; root.mkdir()
    command(root, "init", "-q")
    (root/"feature.py").write_text("def limit():\n    return 1\n", encoding="utf-8")
    base = commit(root, "Start feature")
    (root/"feature.py").write_text("def limit():\n    return 3\n", encoding="utf-8")
    (root/".env").write_text("PRIVATE_VALUE=never-send-this", encoding="utf-8")
    (root/"package-lock.json").write_text('{"version":2}', encoding="utf-8")
    (root/"image.png").write_bytes(b"\x00\x01\x02")
    head = commit(root, "Change limit; untrusted commit message is data")
    return root, base, head


def selection(git_repository):
    root, base, head = git_repository
    return git_import.PreviewInput(repo_path=str(root), base=base, head=head, files=["feature.py"])


def test_inspect_recent_pins_range_and_reports_omissions(git_repository, monkeypatch):
    root, base, head = git_repository
    (root/"uncommitted.py").write_text("PRIVATE WORKING TREE", encoding="utf-8")
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: pytest.fail("Inspect must not infer"))
    data = git_import.inspect(git_import.InspectInput(repo_path=str(root), count=1))
    assert data["base"] == base and data["head"] == head and data["worktree_dirty"]
    files = {f["path"]: f for f in data["files"]}
    assert files["feature.py"]["eligible"]
    assert files[".env"]["reason"] == "Sensitive filename"
    assert files["package-lock.json"]["reason"] == "Generated or dependency file"
    assert not files["image.png"]["eligible"]
    assert "uncommitted.py" not in files


def test_root_baseline_and_explicit_range(git_repository):
    root, base, head = git_repository
    data = git_import.inspect(git_import.InspectInput(repo_path=str(root), count=10))
    assert data["base"] == "" and data["commit_count"] == 2
    bundle = git_import.preview(git_import.PreviewInput(repo_path=str(root), base="", head=head, files=["feature.py"]))
    assert "return 3" in bundle["evidence"][0]["diff"]
    explicit = git_import.inspect(git_import.InspectInput(repo_path=str(root), mode="range", base=base, head=head))
    assert explicit["commit_count"] == 1
    with pytest.raises(generator.GenerationError):
        git_import.inspect(git_import.InspectInput(repo_path=str(root), mode="range", base=head, head=base))


def test_preview_excludes_unselected_data_and_external_drivers(git_repository, tmp_path):
    root, base, head = git_repository
    marker = tmp_path/"should-not-exist"
    command(root, "config", "diff.external", "invalid-external-diff-command")
    command(root, "config", "diff.test.textconv", "invalid-textconv-command")
    (root/".gitattributes").write_text("*.py diff=test\n", encoding="utf-8")
    bundle = git_import.preview(selection(git_repository))
    raw = json.dumps(bundle)
    assert "never-send-this" not in raw and "return 3" in raw
    assert bundle["source_context"]["partial"] and ".env" in bundle["source_context"]["omitted_files"]
    assert not marker.exists()
    with pytest.raises(generator.GenerationError):
        git_import.preview(git_import.PreviewInput(repo_path=str(root), base=base, head=head, files=[".env"]))


@pytest.mark.parametrize("bad", ["../feature.py", ":(glob)*", "/feature.py", "feature.py\nother"])
def test_invalid_paths_never_reach_model(git_repository, bad, monkeypatch):
    root, base, head = git_repository
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: pytest.fail("No model call"))
    with pytest.raises((generator.GenerationError, ValueError)):
        git_import.preview(git_import.PreviewInput(repo_path=str(root), base=base, head=head, files=[bad]))


@pytest.mark.parametrize("content", ["x"*(git_import.MAX_FILE_BYTES+1), "access_token = 'ghp_" + "a"*30 + "'\n"], ids=["read-limit", "credential"])
def test_oversized_and_credential_diffs_fail_before_inference(git_repository, content, monkeypatch):
    root, base, head = git_repository
    (root/"feature.py").write_text(content, encoding="utf-8")
    head = commit(root, "Controlled unsafe fixture")
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: pytest.fail("No model call"))
    with pytest.raises(generator.GenerationError):
        git_import.preview(git_import.PreviewInput(repo_path=str(root), base=base, head=head, files=["feature.py"]))


def test_extract_one_call_preserves_raw_and_rejects_bad_provenance(git_repository, monkeypatch):
    picked = selection(git_repository); bundle = git_import.preview(picked)
    calls = []
    raw = {"done": True, "model": "MOCK", "message": {"content": json.dumps({"facts": [
        {"text": "The configured limit changed from 1 to 3.", "evidence_ids": ["D01"], "kind": "implemented"}]})}}
    def model(path, payload, timeout): calls.append(payload); return raw
    monkeypatch.setattr(generator, "ollama_json", model)
    request = git_import.ExtractInput(**picked.model_dump(), reviewed=True, preview_sha256=bundle["preview_sha256"])
    data = git_import.extract(request)
    assert data["raw_response"] == raw and data["review_required"] and len(calls) == 1
    assert "never-send-this" not in json.dumps(calls) and "untrusted commit message" not in json.dumps(calls)
    with pytest.raises(generator.GenerationError):
        git_import.extract(request.model_copy(update={"preview_sha256": "f"*64}))
    assert len(calls) == 1
    raw["message"]["content"] = json.dumps({"facts": [{"text": "Wrong.", "evidence_ids": ["D99"], "kind": "fix"}]})
    with pytest.raises(generator.GenerationError) as error:
        git_import.extract(request)
    assert error.value.evidence["raw_response"] == raw and len(calls) == 2


def test_api_invalid_refs_and_unreviewed_request_do_not_infer(git_repository, monkeypatch):
    root, base, head = git_repository
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **kw: pytest.fail("No model call"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.post("/api/git/inspect", json={"repo_path": str(root), "mode": "range", "base": "--help"}).status_code == 422
        assert client.post("/api/git/facts", json={**selection(git_repository).model_dump(), "reviewed": False, "preview_sha256": "a"*64}).status_code == 422


def test_git_sources_cannot_become_a_release(git_repository, input_data):
    from patchpitch.models import PitchInput
    bundle = git_import.preview(selection(git_repository))
    with pytest.raises(ValueError, match="committed code"):
        PitchInput.model_validate({**input_data, "source_context": bundle["source_context"]})
    request = PitchInput.model_validate({**input_data, "source_context": bundle["source_context"], "writing_goal": "development"})
    assert "DEVELOPMENT PROGRESS" in generator.build_payload(request)["messages"][0]["content"]


@pytest.mark.parametrize("damage", [None, "diff", "fact", "range", "selection"])
def test_saved_git_review_validates_immutable_evidence(git_repository, damage):
    from patchpitch.sessions import GitReview
    picked = selection(git_repository)
    inspected = git_import.inspect(git_import.InspectInput(repo_path=picked.repo_path, mode="range", base=picked.base, head=picked.head))
    saved = {"inspection": inspected, "preview": git_import.preview(picked), "record": None,
        "selected_files": ["feature.py"], "facts": [{"text": "The limit changed.", "current_text": "Мои правки.\n",
            "include": True, "kind": "implemented", "evidence_ids": ["D01"]}]}
    if damage == "diff": saved["preview"]["evidence"][0]["diff"] += "unreviewed"
    if damage == "fact": saved["facts"][0]["evidence_ids"] = ["D99"]
    if damage == "range": saved["preview"]["source_context"]["head"] = "f"*40
    if damage == "selection": saved["selected_files"] = [".env"]
    if damage:
        with pytest.raises(ValueError): GitReview.model_validate(saved)
    else:
        assert GitReview.model_validate(saved).facts[0].current_text == "Мои правки.\n"


def test_merge_range_uses_net_diff_without_duplicate_file_evidence(git_repository):
    root, _, start = git_repository
    branch = command(root, "branch", "--show-current")
    command(root, "checkout", "-qb", "topic")
    (root/"topic.py").write_text("topic = 1\n", encoding="utf-8"); commit(root, "Topic change")
    command(root, "checkout", branch)
    (root/"main.py").write_text("main = 1\n", encoding="utf-8"); commit(root, "Main change")
    command(root, "-c", "user.name=PatchPitch test", "-c", "user.email=patchpitch@example.invalid", "merge", "--no-ff", "topic", "-m", "Merge topic")
    head = command(root, "rev-parse", "HEAD")
    data = git_import.inspect(git_import.InspectInput(repo_path=str(root), mode="range", base=start, head=head))
    assert data["commit_count"] == 3
    assert sorted(f["path"] for f in data["files"]) == ["main.py", "topic.py"]
    bundle = git_import.preview(git_import.PreviewInput(repo_path=str(root), base=start, head=head, files=["main.py", "topic.py"]))
    assert len(bundle["evidence"]) == 2


def test_reverted_work_is_not_proposed_as_a_net_feature(git_repository):
    root, base, changed = git_repository
    command(root, "-c", "user.name=PatchPitch test", "-c", "user.email=patchpitch@example.invalid", "revert", "--no-edit", changed)
    head = command(root, "rev-parse", "HEAD")
    data = git_import.inspect(git_import.InspectInput(repo_path=str(root), mode="range", base=base, head=head))
    assert data["commit_count"] == 2 and data["files"] == []


@pytest.mark.parametrize("endpoint", ["/api/pitch", "/api/social"])
def test_full_git_provenance_fits_generation_transport(endpoint, input_data, monkeypatch):
    from patchpitch import social
    from patchpitch.models import PitchInput, SocialInput
    omitted = [f"src/{i:03}/"+"a"*250+".py" for i in range(199)]
    body = {**input_data, "format": "devlog" if endpoint.endswith("pitch") else "x_thread",
        "writing_goal": "development", "source_context": {"kind": "git", "repository": "test",
        "repository_id": "a"*64, "base": "b"*40, "head": "c"*40, "commit_count": 1,
        "worktree_dirty": False, "omitted_files": omitted, "partial": True}}
    (PitchInput if endpoint.endswith("pitch") else SocialInput).model_validate(body)
    assert len(json.dumps(body).encode()) > 32_000
    monkeypatch.setattr(generator if endpoint.endswith("pitch") else social, "generate",
        lambda request: {"source_context": request.source_context.model_dump()})
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(endpoint, json=body)
    assert response.status_code == 200
    assert response.json()["source_context"]["omitted_files"] == omitted


@pytest.fixture
def large_git_repository(git_repository):
    root, _, base = git_repository
    (root/"feature.py").write_text("".join(f"value_{i} = 'committed line {i} with useful context'\n" for i in range(750)), encoding="utf-8")
    head = commit(root, "Implement a large file change")
    return root, base, head


def test_large_file_preview_is_complete_and_model_calls_are_bounded(large_git_repository, monkeypatch):
    from patchpitch import git_chunks
    root, base, head = large_git_repository
    inspected = git_import.inspect(git_import.InspectInput(repo_path=str(root), count=1))
    assert inspected["files"][0]["eligible"]  # More than the former 500-line cap.
    picked = git_import.PreviewInput(repo_path=str(root), base=base, head=head, files=["feature.py"])
    bundle = git_import.preview(picked)
    expected = subprocess.check_output(["git","-C",str(root),"diff","--no-ext-diff","--no-textconv","--no-renames","--unified=2",base,head,"--","feature.py"])
    assert b"".join(e["diff"].encode() for e in bundle["evidence"]) == expected
    assert len(bundle["chunking"]["batches"]) > 1
    calls = []
    def model(path, payload, timeout):
        calls.append(payload)
        ids = payload["format"]["$defs"]["Candidate"]["properties"]["evidence_ids"]["items"]["enum"]
        return {"done":True,"model":"MOCK","message":{"content":json.dumps({"facts":[
            {"text":"Committed values were added.","kind":"implemented","evidence_ids":[ids[0]]}]})}}
    monkeypatch.setattr(generator,"ollama_json",model)
    for batch in bundle["chunking"]["batches"]:
        response = git_import.extract(git_import.ExtractInput(**picked.model_dump(),reviewed=True,
            preview_sha256=bundle["preview_sha256"],batch_index=batch["index"]))
        assert response["batch"]["evidence_ids"] == batch["evidence_ids"]
        assert [e["id"] for e in response["evidence"]] == batch["evidence_ids"]
        assert response["review_required"]
        assert len(json.dumps(response["evidence"],ensure_ascii=False).encode()) <= git_chunks.BATCH_BYTES
    assert len(calls) == len(bundle["chunking"]["batches"])
    assert all(call["options"]["num_ctx"] >= 24_576 for call in calls)
    # An unrelated dirty tree change does not invalidate immutable reviewed chunks.
    (root/"scratch.py").write_text("private uncommitted data",encoding="utf-8")
    assert git_import.preview(picked)["preview_sha256"] == bundle["preview_sha256"]
    assert "private uncommitted data" not in json.dumps(calls)


def test_late_credential_or_wrong_batch_citation_never_becomes_a_fact(large_git_repository, monkeypatch):
    root, base, head = large_git_repository
    picked = git_import.PreviewInput(repo_path=str(root),base=base,head=head,files=["feature.py"])
    bundle = git_import.preview(picked)
    other = bundle["evidence"][-1]["id"]
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:{"done":True,"message":{"content":json.dumps({"facts":[
        {"text":"Unsupported later code.","kind":"implemented","evidence_ids":[other]}]})}})
    with pytest.raises(generator.GenerationError) as error:
        git_import.extract(git_import.ExtractInput(**picked.model_dump(),reviewed=True,preview_sha256=bundle["preview_sha256"]))
    assert error.value.evidence["raw_response"] is not None
    with (root/"feature.py").open("a",encoding="utf-8") as f:
        f.write("\naccess_token = 'ghp_"+"a"*30+"'\n")
    head = commit(root,"Sensitive test fixture at the end")
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:pytest.fail("All files must be scanned before the first batch"))
    with pytest.raises(generator.GenerationError,match="possible credential"):
        git_import.preview(picked.model_copy(update={"head":head}))


def test_empty_batch_and_invalid_batch_index(large_git_repository, monkeypatch):
    root, base, head = large_git_repository
    picked=git_import.PreviewInput(repo_path=str(root),base=base,head=head,files=["feature.py"])
    bundle=git_import.preview(picked)
    calls=[]
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:calls.append(1) or {"done":True,"message":{"content":'{"facts":[]}'}})
    request=git_import.ExtractInput(**picked.model_dump(),reviewed=True,preview_sha256=bundle["preview_sha256"])
    assert git_import.extract(request)["facts"] == []
    with pytest.raises(generator.GenerationError):
        git_import.extract(request.model_copy(update={"batch_index":23}))
    assert len(calls)==1


def test_large_root_baseline_preserves_the_entire_committed_blob(large_git_repository):
    root,_,head=large_git_repository
    preview=git_import.preview(git_import.PreviewInput(repo_path=str(root),base="",head=head,files=["feature.py"]))
    expected=b"New file at root baseline:\n"+subprocess.check_output(["git","-C",str(root),"show",head+":feature.py"])
    assert b"".join(e["diff"].encode() for e in preview["evidence"])==expected
    assert len(preview["evidence"])>1


@pytest.mark.parametrize("damage", [None,"completed","citation","original","candidate","checkpoint","repository"], ids=["valid","completion","citation","original","edited-original","order","repo"])
def test_partial_git_session_preserves_edits_and_validates_checkpoints(large_git_repository, monkeypatch, damage):
    from patchpitch.sessions import GitReview
    root, base, head=large_git_repository
    picked=git_import.PreviewInput(repo_path=str(root),base=base,head=head,files=["feature.py"])
    preview=git_import.preview(picked)
    monkeypatch.setattr(generator,"ollama_json",lambda *a,**kw:{"done":True,"model":"MOCK","message":{"content":json.dumps({"facts":[
        {"text":"A reviewed addition.","kind":"implemented","evidence_ids":["D01"]}]})}})
    response=git_import.extract(git_import.ExtractInput(**picked.model_dump(),reviewed=True,preview_sha256=preview["preview_sha256"]))
    run={"schema_version":2,"kind":"patchpitch_git_review","status":"partial",**preview,
        "attempts":[{"batch_index":0,"status":"accepted","response":response,"error":None},
            {"batch_index":1,"status":"failed","response":{"raw_response":{"message":{"content":"Rejected original"}}},
                "error":{"code":"invalid_draft","message":"Rejected batch"}}]}
    facts=[{**f,"batch_index":0,"current_text":"Мои точные правки.\n","include":True} for f in response["facts"]]
    saved={"inspection":git_import.inspect(git_import.InspectInput(repo_path=str(root),count=1)),
        "preview":preview,"facts":facts,"record":run,"selected_files":["feature.py"]}
    if damage=="completed": run["status"]="complete"
    if damage=="citation": response["facts"][0]["evidence_ids"]=[preview["evidence"][-1]["id"]]
    if damage=="original": response["raw_response"]["message"]["content"]='{"facts":[]}'
    if damage=="candidate": facts[0]["text"]="Changed original candidate"
    if damage=="checkpoint": run["attempts"][1]["batch_index"]=0
    if damage=="repository": response["source_context"]={**response["source_context"],"repository_id":"f"*64}
    if damage:
        with pytest.raises(ValueError): GitReview.model_validate(saved)
    else:
        checked=GitReview.model_validate(saved)
        assert checked.facts[0].current_text=="Мои точные правки.\n"


def test_legacy_saved_diff_remains_openable(git_repository):
    from patchpitch import git_chunks
    from patchpitch.sessions import GitReview
    picked=selection(git_repository)
    preview=git_import.preview(picked)
    preview.pop("chunking")
    preview["preview_sha256"]=git_chunks.preview_hash(picked.base,picked.head,preview["evidence"])
    saved={"inspection":git_import.inspect(git_import.InspectInput(repo_path=picked.repo_path,count=1)),
        "preview":preview,"facts":[{"text":"Old saved fact.","current_text":"Exact edit.\n","include":True,"kind":"implemented","evidence_ids":["D01"]}],
        "record":None,"selected_files":["feature.py"]}
    assert GitReview.model_validate(saved).facts[0].current_text=="Exact edit.\n"
