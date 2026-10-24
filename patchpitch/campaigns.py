"""Persistent unattended campaigns; the web server is never imported here."""
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import generator, git_import, sessions, social
from .build import source_hash
from .fact_packs import FactPack, prepare_pack
from .jobs import Job, load_config, local_path, validate_model
from .models import PitchInput, SocialInput
from .run_store import FileLock, RunError, digest, read_json, write_json, write_text


def now():
    return datetime.now(timezone.utc).isoformat()


def runtime():
    from . import __version__
    return {"source_sha256": source_hash(), "model": generator.MODEL,
            "options": generator.OPTIONS, "timeout": generator.TIMEOUT, "version": __version__}


def failure(exc):
    if isinstance(exc, RunError):
        return exc.as_dict(), exc.exit_code
    if isinstance(exc, generator.GenerationError):
        return {"code": exc.code, "message": exc.message}, 3 if exc.status in {409, 503} else 4
    raise exc


def snapshot(job_path):
    job_path = Path(job_path).resolve()
    job = validate_model(Job, load_config(job_path))
    base = job_path.parent
    profile = validate_model(sessions.Profile, read_json(local_path(base, job.product_profile))).model_dump()
    result = {"job": job.model_dump(), "profile": profile, "runtime": runtime(), "voices": {}, "catalogs": {}}
    if job.source.kind == "reviewed_fact_pack":
        pack = validate_model(FactPack, read_json(local_path(base, job.source.path)))
        prepared = prepare_pack(pack)
        for change, fact in zip(prepared["changes"], pack.facts):
            change["include"] = fact.include and (fact.kind == "released" or
                                (job.writing_goal == "development" and fact.kind == "internal"))
        if not any(c["include"] for c in prepared["changes"]):
            raise RunError("NO_SELECTED_FACTS", "The job selects no eligible reviewed facts.")
        prepared["context_overrides"] = [key for key in ("product", "audience", "cta_text") if prepared[key] != profile[key]]
        prepared.update({key: profile[key] for key in ("product", "audience", "cta_text")})
        result["source"] = {"kind": job.source.kind, "prepared": prepared, "review_status": "reviewed"}
    else:
        root = git_import.repo(str(local_path(base, job.source.repository)))
        head = git_import.resolve(root, job.source.head)
        baseline = git_import.resolve(root, job.source.base) if job.source.base else ""
        if head == baseline:
            result["source"] = {"kind": "git_range", "no_changes": True, "head": head, "base": baseline}
        else:
            request = git_import.PreviewInput(repo_path=str(root), base=baseline, head=head, files=job.source.files)
            preview = git_import.preview(request)
            selection_path = local_path(base, job.source.selection_file) if job.source.selection_file else None
            selection = read_json(selection_path) if selection_path else None
            if selection is not None and selection.get("preview_sha256") != preview["preview_sha256"]:
                raise RunError("STALE_SELECTION", "The saved fact selection belongs to different diffs.")
            if selection is not None and selection.get("candidates_file"):
                pool = read_json(local_path(selection_path.parent, selection["candidates_file"]))
                if pool.get("preview_sha256") != preview["preview_sha256"] or digest(pool.get("facts")) != selection.get("candidate_sha256"):
                    raise RunError("STALE_CANDIDATES", "The selected candidate file has a different source or content digest.")
                selection["candidate_pool"] = pool["facts"]
            result["source"] = {"kind": "git_range", "request": request.model_dump(), "preview": preview,
                                "selection": selection, "review_status": "machine_selected_unreviewed"}
    for target in job.targets:
        try:
            if target.voice:
                from .voice import prepare_voice
                result["voices"][target.id] = {"bundle": prepare_voice(job.voices[target.voice], base,
                                               language=target.language, format=target.format)}
            if target.hashtag_catalog:
                from .hashtags import Catalog
                catalog = validate_model(Catalog, read_json(local_path(base, target.hashtag_catalog), 1_000_000))
                result["catalogs"][target.id] = catalog.model_dump()
        except (RunError, generator.GenerationError) as exc:
            result["voices"][target.id] = {"error": failure(exc)[0], "exit_code": failure(exc)[1]}
    return result


def summary(path, manifest):
    return {"schema_version": "patchpitch.summary/v1", "run_id": manifest["run_id"],
            "status": manifest["status"], "targets": manifest["targets"],
            "artifacts": {"run": str(Path(path).resolve()), "manifest": str(Path(path).resolve() / "manifest.json")},
            "errors": manifest.get("errors", []), "warnings": manifest.get("warnings", []),
            "model_requests": manifest.get("requests_used", 0)}


def planned(snap):
    job = validate_model(Job, snap["job"])
    no_changes = snap["source"].get("no_changes", False)
    batches = len(snap["source"].get("preview", {}).get("chunking", {}).get("batches", []))
    requests = 0 if no_changes else batches + sum(2 if t.channel == "x" else 1 for t in job.targets)
    errors = [v["error"] for v in snap["voices"].values() if "error" in v]
    if requests > job.execution.max_model_requests:
        errors.append({"code": "REQUEST_BUDGET_EXCEEDED", "message": "The plan exceeds max_model_requests."})
    return {"schema_version": "patchpitch.summary/v1", "run_id": job.campaign_id, "status": "invalid_plan" if errors else "planned",
            "targets": {t.id: {"status": "pending", "format": t.format} for t in job.targets},
            "artifacts": {}, "errors": errors, "warnings": ["Plan performs no inference; model availability is checked by the actual request."],
            "model_requests": requests, "exit_code": 2 if errors else 0}


class Runner:
    def __init__(self, path, snap, manifest):
        self.path, self.snap, self.manifest = Path(path), snap, manifest
        self.job = validate_model(Job, snap["job"])

    def save(self):
        self.manifest["updated_at"] = now()
        write_json(self.path / "manifest.json", self.manifest)

    def call(self, step, request, fn):
        input_snapshot = request.model_dump() if hasattr(request, "model_dump") else request
        for saved in sorted((self.path / "attempts").glob("*.json"), reverse=True):
            attempt = read_json(saved)
            if attempt["step"] == step and attempt["status"] == "accepted" and digest(attempt["input_snapshot"]) == digest(input_snapshot):
                return attempt["response"]
        if self.manifest["requests_used"] >= self.job.execution.max_model_requests:
            raise RunError("REQUEST_BUDGET_EXCEEDED", "The run exhausted max_model_requests.", 4)
        self.manifest["requests_used"] += 1
        attempt_id = f"A{self.manifest['requests_used']:04}"
        path = self.path / "attempts" / f"{attempt_id}.json"
        attempt = {"id": attempt_id, "step": step, "status": "running", "recorded_at": now(),
                   "input_snapshot": input_snapshot,
                   "configured_model": generator.MODEL, "response": None, "error": None}
        write_json(path, attempt)
        self.save()
        print(f"{step}: {attempt_id}", file=sys.stderr, flush=True)
        try:
            response = fn(request)
        except (RunError, generator.GenerationError) as exc:
            attempt.update(status="failed", error=failure(exc)[0], evidence=getattr(exc, "evidence", None))
            write_json(path, attempt)
            raise
        attempt.update(status="accepted", response=response)
        write_json(path, attempt)
        return response

    def facts(self):
        source = self.snap["source"]
        if source["kind"] == "reviewed_fact_pack":
            prepared = copy.deepcopy(source["prepared"])
        else:
            bundle = source["preview"]
            candidates = []
            selection = source["selection"]
            batches = [] if selection and "candidate_pool" in selection else bundle["chunking"]["batches"]
            for index, batch in enumerate(batches):
                checkpoint = self.path / "facts" / f"batch-{index:02}.json"
                if checkpoint.exists():
                    response = read_json(checkpoint)
                else:
                    # reviewed here records the explicit job authorisation, not a
                    # human semantic review. review_status remains unreviewed.
                    request = git_import.ExtractInput(**source["request"], reviewed=True,
                                  preview_sha256=bundle["preview_sha256"], batch_index=index)
                    response = self.call(f"git:{index}", request, git_import.extract)
                    write_json(checkpoint, response)
                for n, fact in enumerate(response["facts"]):
                    candidates.append({**fact, "id": f"B{index:02}F{n:02}"})
            if selection and "candidate_pool" in selection:
                candidates = selection["candidate_pool"]
                from .git_import import Candidate
                import re
                for fact in candidates:
                    if not re.fullmatch(r"B[0-9]{2}F[0-9]{2}", fact.get("id", "")):
                        raise RunError("INVALID_SELECTION", "Invalid saved candidate identity.")
                    validate_model(Candidate, {k: v for k, v in fact.items() if k != "id"})
                    if not set(fact["evidence_ids"]) <= {e["id"] for e in bundle["evidence"]}:
                        raise RunError("INVALID_SELECTION", "Saved candidate cites evidence outside this preview.")
            candidate_hash = digest(candidates)
            write_json(self.path / "facts" / "candidates.json", {"preview_sha256": bundle["preview_sha256"], "candidate_sha256": candidate_hash, "facts": candidates})
            if selection is not None:
                if selection.get("candidate_sha256") != candidate_hash:
                    raise RunError("STALE_CANDIDATES", "The selection does not match these exact extracted candidates.", 4)
                ids = selection.get("selected_ids")
                if (not isinstance(ids, list) or any(not isinstance(x, str) for x in ids) or
                        len(set(ids)) != len(ids) or not set(ids) <= {f["id"] for f in candidates}):
                    raise RunError("INVALID_SELECTION", "Selection must name unique candidate IDs from these exact diffs.")
                candidates = [f for f in candidates if f["id"] in ids]
            else:
                candidates = [f for f in candidates if f["kind"] != "uncertain"]
            if not candidates:
                raise RunError("NO_SELECTED_FACTS", "Extraction produced no eligible facts.", 4)
            if len(candidates) > 15 or sum(len(f["text"]) for f in candidates) > 6000:
                raise RunError("FACT_BUDGET_EXCEEDED", "Candidates exceed 15 facts / 6000 characters; use a selection_file.", 4)
            evidence = {e["id"]: e for e in bundle["evidence"]}
            prepared = {"changes": [{"id": f"C{i:02}", "text": f["text"], "include": True, "reason": "Machine selected; semantic review required"}
                                    for i, f in enumerate(candidates, 1)],
                        "source_references": [{"api_id": f"C{i:02}", "stable_id": f["id"], "source_url": "",
                            "source_ref": "; ".join(evidence[e]["path"] + ":" + e for e in f["evidence_ids"])} for i, f in enumerate(candidates, 1)],
                        "source_context": bundle["source_context"], "release_label": bundle["source_context"]["head"][:12],
                        "voice_reference": "", "pack_id": "", "pack_version": "", "pack_sha256": "", "context_overrides": []}
            prepared.update({key: self.snap["profile"][key] for key in ("product", "audience", "cta_text")})
        prepared.update(writing_goal=self.job.writing_goal, review_status=source["review_status"])
        write_json(self.path / "sources.json", prepared)
        return prepared

    def target(self, target, facts):
        directory = self.path / "outputs" / target.id
        voice_state = self.snap["voices"].get(target.id, {})
        if "error" in voice_state:
            err = voice_state["error"]
            raise RunError(err["code"], err["message"], voice_state["exit_code"])
        data = {key: value for key, value in facts.items() if key not in {"review_required", "review_status"}}
        data["changes"] = [{k: c[k] for k in ("id", "text", "include")} for c in facts["changes"]]
        data.update(confirmed=True, format=target.format, language=target.language, auto_tags=False,
                    style="voice" if target.voice else target.style or "clear")
        if target.voice:
            data.update(voice_bundle=voice_state["bundle"], voice_reference="",
                        voice_register=self.job.voices[target.voice].register_name)
            write_json(self.path / "voices" / f"{target.id}.json", voice_state["bundle"])
        if target.channel == "x":
            from .hashtags import generate_campaign
            data.update(post_count=target.post_count, intent=target.intent)
            request = validate_model(SocialInput, data)
            result = generate_campaign(request, self.snap["catalogs"][target.id],
                                       lambda step, req, fn: self.call(target.id + ":" + step, req, fn), directory)
        elif target.channel in {"dev", "github"}:
            from .longform import LongformInput, generate
            request = validate_model(LongformInput, data)
            result = self.call(target.id, request, generate)
        else:
            request = validate_model(PitchInput, data)
            result = self.call(target.id, request, generator.generate)
        result["editorial_status"] = facts["review_status"]
        result["context"]["target_id"] = target.id
        if not (directory / "original.json").exists():
            write_json(directory / "original.json", result)
        # The current result is deliberately separate from immutable generation.
        if not (directory / "current.json").exists():
            write_json(directory / "current.json", result)
        export_result(directory, result, preserve_existing=True)
        write_json(directory / "validation.json", {"status": "passed", "checked_at": now(), "editorial_status": facts["review_status"]})

    def execute(self):
        self.manifest["errors"] = []
        if self.snap["source"].get("no_changes"):
            self.manifest["status"] = "no_changes"
            self.save()
            return summary(self.path, self.manifest), 0
        try:
            facts = self.facts()
        except (RunError, generator.GenerationError) as exc:
            error, code = failure(exc)
            self.manifest.update(status="failed", errors=[error])
            for target in self.manifest["targets"].values():
                target.update(status="blocked", error=error)
            self.save()
            return summary(self.path, self.manifest), code
        exit_code = 0
        stopped = False
        for target in self.job.targets:
            state = self.manifest["targets"][target.id]
            if state["status"] == "succeeded":
                continue
            if stopped:
                state.update(status="blocked", error={"code": "EARLIER_TARGET_FAILED", "message": "Job stops after a target failure."})
                continue
            state.update(status="running", error=None)
            self.save()
            try:
                self.target(target, facts)
                state.update(status="succeeded", editorial_status=facts["review_status"])
            except (RunError, generator.GenerationError) as exc:
                error, code = failure(exc)
                state.update(status="failed", error=error)
                self.manifest["errors"].append({"target": target.id, **error})
                exit_code = max(exit_code, code)
                stopped = not self.job.execution.continue_other_targets_on_error
            self.save()
        states = [s["status"] for s in self.manifest["targets"].values()]
        self.manifest["status"] = "succeeded" if all(s == "succeeded" for s in states) else "partial_failure" if "succeeded" in states else "failed"
        self.save()
        return summary(self.path, self.manifest), exit_code


def export_result(directory, result, preserve_existing=False):
    directory = Path(directory)
    def save_text(name, content):
        if not preserve_existing or not (directory / name).exists():
            write_text(directory / name, content)
    if result["presentation"]["format"].startswith("x_"):
        posts = result["draft"]["posts"]
        text = "\n\n---\n\n".join(p["text"] for p in posts) + "\n"
        for post in posts:
            save_text(f"{post['id']}.txt", post["text"] + "\n")
    else:
        text = result["markdown"]
    save_text("draft.md", text)
    if result["presentation"]["format"] == "dev_article":
        body = result["draft"]["text"] + ("\n\n" + result["input_snapshot"]["cta_text"] if result["input_snapshot"]["cta_text"] else "")
        save_text("article.md", body + "\n")
        if not preserve_existing or not (directory / "article.json").exists():
            write_json(directory / "article.json", {"title": result["draft"]["title"], "description": result["draft"]["description"],
                        "tags": result["draft"]["tags"], "published": False})
    if result["presentation"]["format"] == "github_release_notes":
        save_text("release-notes.md", text)
        write_json(directory / "release-notes.json", {"version": result["context"]["release_label"],
                   "source_context": result["context"].get("source_context"), "source_map": result["source_map"]})


def run(job_path, out=None, plan=False, out_root=None):
    snap = snapshot(job_path)
    if plan:
        value = planned(snap)
        return value, value.pop("exit_code")
    if out is None and out_root is None:
        raise RunError("OUTPUT_REQUIRED", "Choose --out or --out-root.")
    path = Path(out).resolve() if out is not None else Path(out_root).resolve() / snap["job"]["campaign_id"] / digest(snap)[:20]
    path.mkdir(parents=True, exist_ok=True)
    with FileLock(path / ".run.lock"):
        manifest_path = path / "manifest.json"
        identity = digest(snap)
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            if manifest.get("input_sha256") != identity:
                raise RunError("RUN_INPUT_MISMATCH", "This output directory belongs to different inputs/runtime; choose a new directory.")
            if manifest["status"] in {"succeeded", "no_changes"}:
                return summary(path, manifest), 0
            value = summary(path, manifest)
            value["warnings"].append("Use resume to explicitly continue this incomplete run.")
            return value, 4
        if any(p.name != ".run.lock" for p in path.iterdir()):
            raise RunError("OUTPUT_NOT_EMPTY", "Select an empty output directory for a new campaign.")
        manifest = {"schema_version": "patchpitch.run/v1", "run_id": snap["job"]["campaign_id"], "input_sha256": identity,
                    "created_at": now(), "status": "running", "requests_used": 0, "errors": [], "warnings": [],
                    "targets": {t["id"]: {"format": t["format"], "status": "pending"} for t in snap["job"]["targets"]}}
        write_json(path / "snapshot.json", snap)
        runner = Runner(path, snap, manifest)
        runner.save()
        return runner.execute()


def resume(path):
    path = Path(path).resolve()
    with FileLock(path / ".run.lock"):
        snap, manifest = read_json(path / "snapshot.json"), read_json(path / "manifest.json")
        if digest(snap) != manifest["input_sha256"] or snap["runtime"] != runtime():
            raise RunError("RUN_INPUT_MISMATCH", "The saved snapshot or current runtime differs from this run.")
        if manifest["status"] in {"succeeded", "no_changes"}:
            return summary(path, manifest), 0
        for attempt_path in sorted((path / "attempts").glob("*.json")):
            attempt = read_json(attempt_path)
            if attempt["status"] == "running":
                attempt.update(status="interrupted", error={"code": "INTERRUPTED", "message": "No completed response was checkpointed."})
                write_json(attempt_path, attempt)
        return Runner(path, snap, manifest).execute()
