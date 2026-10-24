"""Offline automation contracts. Synthetic observations are not reach evidence."""
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from patchpitch import campaigns, generator, sessions
from patchpitch.campaign_export import export_session, validate_run
from patchpitch.cli import main
from patchpitch.hashtags import Catalog, select, validate_text
from patchpitch.jobs import Job
from patchpitch.models import SocialInput
from patchpitch.run_store import FileLock, RunError, read_json, write_json


def catalog_data():
    observed = datetime.now(timezone.utc).isoformat()
    return {"schema_version": "patchpitch.hashtag-catalog/v1", "id": "synthetic-test-only", "version": "1",
        "max_age_days": 30, "tags": [{"tag": t, "languages": ["en", "ru"], "keywords": ["local"],
            "audience_keywords": ["developers"], "audience_fit": 3,
            "evidence": [{"kind": "public_sample", "source": "https://example.test/synthetic-not-observed",
                "observed_at": observed, "window_days": 7, "sample_size": 10, "relevant_posts": 8, "relevant_authors": 4}]}
            for t in ["#LocalFirst", "#DevTools", "#BuildInPublic", "#LocalAI", "#DeveloperTools", "#WritingTools"]]}


@pytest.fixture
def job_files(tmp_path):
    write_json(tmp_path / "profile.json", {"kind": "patchpitch_profile", "schema_version": 1,
        "product": {"name": "PatchPitch", "description": "Prepare local drafts from selected facts."},
        "audience": "developers", "cta_text": ""})
    write_json(tmp_path / "facts.json", {"schema_version": 1, "id": "test-facts", "version": "1",
        "product": {"name": "PatchPitch", "description": "Prepare local drafts from selected facts."},
        "audience": "developers", "release_label": "development", "facts": [
            {"id": "local_drafts", "text": "PatchPitch prepares local drafts from selected facts.", "include": True,
             "kind": "internal", "source_ref": "Synthetic test input, not release evidence"}]})
    write_json(tmp_path / "catalog.json", catalog_data())
    job = {"schema_version": "patchpitch.job/v1", "campaign_id": "test-campaign", "product_profile": "profile.json",
           "writing_goal": "development", "source": {"kind": "reviewed_fact_pack", "path": "facts.json"},
           "targets": [{"id": "telegram", "channel": "telegram", "format": "telegram"},
                       {"id": "dev", "channel": "dev", "format": "dev_article"},
                       {"id": "github", "channel": "github", "format": "github_release_notes"},
                       {"id": "x", "channel": "x", "format": "x_single", "hashtag_catalog": "catalog.json", "hashtag_policy": "x-six-v1"}]}
    write_json(tmp_path / "job.json", job)
    return tmp_path / "job.json", tmp_path / "run", job


@pytest.fixture
def transport(monkeypatch):
    calls = []
    def answer(path, payload, **kwargs):
        assert path == "/api/chat"
        calls.append(copy.deepcopy(payload))
        if "posts" in payload["format"]["properties"]:
            count = payload["format"]["properties"]["posts"]["maxItems"]
            raw = {"posts": [{"text": "PatchPitch prepares local drafts.", "source_ids": ["C01"]} for _ in range(count)]}
        elif "title" in payload["format"]["properties"]:
            raw = {"title": "Preparing local drafts", "description": "A synthetic offline test.", "sections": [{"heading": "", "paragraphs": [{"text": "PatchPitch prepares local drafts from selected facts.", "source_ids": ["C01"]}], "code_source_ids": []}], "tags": ["devtools"]}
        else:
            raw = {"text": "PatchPitch prepares local drafts from selected facts.", "source_ids": ["C01"], "hashtags": []}
        return {"done": True, "model": "TEST_ONLY", "message": {"content": json.dumps(raw)}}
    monkeypatch.setattr(generator, "ollama_json", answer)
    return calls


def test_plan_no_inference_and_complete_four_channel_run(job_files, transport):
    job, out, _ = job_files
    value, code = campaigns.run(job, out, plan=True)
    assert code == 0 and value["model_requests"] == 5 and not transport and not out.exists()
    value, code = campaigns.run(job, out)
    assert code == 0 and value["status"] == "succeeded" and len(transport) == 5
    assert read_json(out / "sources.json")["changes"][0]["include"] is True
    assert len(list((out / "attempts").glob("*.json"))) == 5
    validate_text((out / "outputs/x/P01.txt").read_text())
    assert read_json(out / "outputs/x/original.json")["planning_record"]["raw_response"]["model"] == "TEST_ONLY"
    assert validate_run(out)[1] == 0
    export_session(out, out / "session.json")
    saved = sessions.Session.model_validate(read_json(out / "session.json"))
    assert len(saved.drafts) == 4 and len(saved.records) == 5
    assert (out / "outputs/dev/article.md").exists()
    assert (out / "outputs/github/release-notes.md").exists()


def test_repeat_preserves_edits_and_never_repeats_inference(job_files, transport):
    job, out, _ = job_files
    campaigns.run(job, out)
    original = (out / "outputs/telegram/original.json").read_bytes()
    (out / "outputs/telegram/draft.md").write_text("My exact local edit.\n", encoding="utf-8")
    assert campaigns.run(job, out)[1] == 0
    assert len(transport) == 5 and (out / "outputs/telegram/original.json").read_bytes() == original
    export_session(out, out / "session.json")
    assert read_json(out / "session.json")["drafts"][0]["markdown"] == "My exact local edit.\n"


def test_failure_resume_keeps_other_targets_and_original_failure(job_files, transport, monkeypatch):
    job, out, _ = job_files
    normal = generator.ollama_json
    def fail_article(path, payload, **kwargs):
        if "title" in payload["format"]["properties"]:
            raise generator.GenerationError("timeout", "TEST timeout", 504)
        return normal(path, payload, **kwargs)
    monkeypatch.setattr(generator, "ollama_json", fail_article)
    value, code = campaigns.run(job, out)
    assert code == 4 and value["status"] == "partial_failure"
    assert value["targets"]["telegram"]["status"] == "succeeded"
    failure_path = out / "attempts/A0002.json"
    failed = failure_path.read_bytes()
    (out / "outputs/telegram/draft.md").write_text("Keep this edit.\n", encoding="utf-8")
    assert campaigns.run(job, out)[1] == 4
    monkeypatch.setattr(generator, "ollama_json", normal)
    assert campaigns.resume(out)[1] == 0
    assert failure_path.read_bytes() == failed
    assert (out / "outputs/telegram/draft.md").read_text() == "Keep this edit.\n"


def test_resume_after_interruption(job_files, transport, monkeypatch):
    job, out, _ = job_files
    normal = generator.ollama_json
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        campaigns.run(job, out)
    assert read_json(out / "attempts/A0001.json")["status"] == "running"
    monkeypatch.setattr(generator, "ollama_json", normal)
    assert campaigns.resume(out)[1] == 0
    assert read_json(out / "attempts/A0001.json")["status"] == "interrupted"


def test_mismatch_rejects_changed_facts_and_job(job_files, transport):
    job, out, _ = job_files
    campaigns.run(job, out)
    facts = read_json(job.parent / "facts.json")
    facts["facts"][0]["text"] += " Another local behavior."
    write_json(job.parent / "facts.json", facts)
    with pytest.raises(RunError, match="different inputs"):
        campaigns.run(job, out)
    assert len(transport) == 5


def test_invalid_json_duplicate_keys_and_unknown_fields(job_files, capsys):
    job, out, data = job_files
    job.write_text('{"schema_version":"patchpitch.job/v1","schema_version":"other"}', encoding="utf-8")
    assert main(["run", "--job", str(job), "--out", str(out), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "DUPLICATE_KEY"
    data["shell"] = "not executable"
    write_json(job, data)
    assert main(["run", "--job", str(job), "--out", str(out), "--json"]) == 2
    assert not out.exists()


def test_cli_stdout_one_json_and_errors(job_files, transport, capsys):
    job, out, _ = job_files
    assert main(["run", "--job", str(job), "--out", str(out), "--json"]) == 0
    streams = capsys.readouterr()
    assert json.loads(streams.out)["status"] == "succeeded" and "telegram:" in streams.err
    assert main(["run", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["errors"][0]["code"] == "ARGUMENT_ERROR"


def test_stale_evidence_blocks_x_only(job_files, transport):
    job, out, _ = job_files
    catalog = read_json(job.parent / "catalog.json")
    for tag in catalog["tags"]:
        tag["evidence"][0]["observed_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    write_json(job.parent / "catalog.json", catalog)
    value, code = campaigns.run(job, out)
    assert code == 4 and value["targets"]["x"]["error"]["code"] == "HASHTAGS_INSUFFICIENT_EVIDENCE"
    assert value["targets"]["telegram"]["status"] == "succeeded"
    assert len(transport) == 4  # Three drafts plus the X plan, no X writing call.


def test_tag_edit_blocks_export_and_topic_change_is_detected(job_files, transport):
    job, out, _ = job_files
    campaigns.run(job, out)
    post = out / "outputs/x/P01.txt"
    original = post.read_text()
    post.write_text(original.replace("#LocalAI", ""), encoding="utf-8")
    assert validate_run(out)[1] == 4
    with pytest.raises(RunError):
        export_session(out, out / "session.json")
    post.write_text(original.replace("PatchPitch prepares local drafts.", "Unrelated topic."), encoding="utf-8")
    report, code = validate_run(out)
    assert code == 4 and report["errors"][0]["code"] == "X_TOPIC_CHANGED"


def test_catalog_requires_real_observation_shape_and_unicode_unique():
    catalog = catalog_data()
    catalog["tags"][0]["evidence"][0]["relevant_posts"] = 11
    with pytest.raises(ValueError):
        Catalog.model_validate(catalog)
    catalog = catalog_data()
    catalog["tags"][1]["tag"] = "#localfirst"
    with pytest.raises(ValueError):
        Catalog.model_validate(catalog)


def test_six_tag_thread_and_length_budget(job_files, transport):
    job, out, data = job_files
    data["targets"] = [data["targets"][-1]]
    data["targets"][0]["format"] = "x_thread"
    data["targets"][0]["post_count"] = 3
    write_json(job, data)
    assert campaigns.run(job, out)[1] == 0
    for post in read_json(out / "outputs/x/original.json")["draft"]["posts"]:
        validate_text(post["text"])
    assert "text_budget" in transport[-1]["messages"][0]["content"]
    assert "#LocalFirst" not in json.loads(transport[-1]["messages"][0]["content"].split("UNTRUSTED DATA:\n")[1])["post_plan"][0]["topic"]


def test_six_tag_model_ceiling_includes_last_card_cta(job_files, transport):
    from patchpitch.social_count import estimate
    job, out, data = job_files
    profile = read_json(job.parent / "profile.json")
    profile["cta_text"] = "https://example.test/project/announcement"
    write_json(job.parent / "profile.json", profile)
    data["targets"] = [data["targets"][-1]]
    data["targets"][0].update(format="x_thread", post_count=3)
    write_json(job, data)
    assert campaigns.run(job, out)[1] == 0
    payload = transport[-1]
    ceiling = payload["format"]["$defs"]["SocialPost"]["properties"]["text"]["maxLength"]
    result = read_json(out / "outputs/x/original.json")
    for index, plan in enumerate(result["input_snapshot"]["hashtag_plan"]):
        full = "a" * ceiling + "\n\n" + " ".join(plan["hashtags"])
        if index == 2:
            full += "\n\n" + profile["cta_text"]
        assert estimate(full)["characters"] <= 280
    assert "150–200" not in payload["messages"][0]["content"]
    assert ceiling < 200


def test_run_and_engine_lock_are_nonblocking(tmp_path):
    path = tmp_path / "lock"
    with FileLock(path):
        with pytest.raises(RunError) as error:
            with FileLock(path):
                pass
        assert error.value.exit_code == 3
    with FileLock(path):
        pass  # Released without deleting the lock file.


def test_resume_recovers_response_committed_before_export(job_files, transport, monkeypatch):
    job, out, data = job_files
    data["targets"] = [data["targets"][0]]
    write_json(job, data)
    export = campaigns.export_result
    monkeypatch.setattr(campaigns, "export_result", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        campaigns.run(job, out)
    assert len(transport) == 1
    (out / "outputs/telegram/draft.md").write_text("An edit after interruption.\n", encoding="utf-8")
    monkeypatch.setattr(campaigns, "export_result", export)
    assert campaigns.resume(out)[1] == 0 and len(transport) == 1
    assert (out / "outputs/telegram/draft.md").read_text() == "An edit after interruption.\n"


def test_scheduled_out_root_uses_input_identity(job_files, transport):
    job, _, _ = job_files
    root = job.parent / "scheduled"
    first, code = campaigns.run(job, out_root=root)
    assert code == 0
    assert campaigns.run(job, out_root=root)[0]["artifacts"] == first["artifacts"]
    assert len(transport) == 5
    facts = read_json(job.parent / "facts.json")
    facts["facts"][0]["source_ref"] += " Updated source identity."
    write_json(job.parent / "facts.json", facts)
    second, code = campaigns.run(job, out_root=root)
    assert code == 0 and second["artifacts"] != first["artifacts"] and len(transport) == 10


@pytest.mark.parametrize("body", ["```toml\n[wrong_schema]\nvalue = 20\n```", "An invented 20% gain.", "### Header\\n- Escaped text.", "Run `patchpitch run --invented-flag now`. Parsed."])
def test_article_rejects_unsourced_examples_and_metrics(body, monkeypatch):
    from patchpitch.longform import LongformInput, generate
    request = LongformInput(product={"name": "PatchPitch", "description": "A local writing tool."}, audience="developers",
                            changes=[{"id": "C01", "text": "Prepare local drafts.", "include": True}], confirmed=True, format="dev_article")
    raw = {"done": True, "message": {"content": json.dumps({"title": "Local drafts", "description": "Writing locally.",
            "sections": [{"heading": "", "paragraphs": [{"text": body, "source_ids": ["C01"]}], "code_source_ids": []}], "tags": []})}}
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **k: raw)
    with pytest.raises(generator.GenerationError) as exc:
        generate(request)
    assert exc.value.code == "invalid_draft" and exc.value.evidence["raw_response"] == raw


def test_article_assembles_paragraphs_and_exact_source_code(monkeypatch):
    from patchpitch.longform import LongformInput, generate
    code = '```text\npython -m patchpitch run --job job.json --out run\n```'
    request = LongformInput(product={"name": "PatchPitch", "description": "A local writing tool."}, audience="developers",
        changes=[{"id": "C01", "text": "Prepare local drafts. Exact usage:\n" + code, "include": True}], confirmed=True, format="dev_article")
    response = {"title": "Local drafts", "description": "Writing locally.", "sections": [{"heading": "Usage",
        "paragraphs": [{"source_ids": ["C01"], "text": "Prepare local drafts."}], "code_source_ids": ["C01"]}], "tags": []}
    monkeypatch.setattr(generator, "ollama_json", lambda *a, **k: {"done": True, "message": {"content": json.dumps(response)}})
    result = generate(request)
    assert result["draft"]["text"] == "## Usage\n\nPrepare local drafts.\n\n" + code
    assert result["raw_draft"] == response
    assert result["article_source_map"][-1]["source_ids"] == ["C01"]
