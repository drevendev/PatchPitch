"""Real Linux inference acceptance run; never delivers to a publication API."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ollama(route):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:11434" + route, timeout=30) as response:
        return json.load(response)


def hashes(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file() and p.suffix != ".lock"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"kind": "LIVE_MODEL", "started_at": datetime.now(timezone.utc).isoformat(),
              "platform": platform.system(), "kernel": platform.release(),
              "machine": platform.machine(), "python": sys.version,
              "source_commit": os.environ.get("GITHUB_SHA"),
              "ci_run": os.environ.get("GITHUB_RUN_ID"), "published": False,
              "stdin": "DEVNULL", "model": os.environ.get("PATCHPITCH_MODEL", "gemma4:12b"),
              "status": "preflight"}
    save(output / "report.json", report)
    if platform.system() != "Linux":
        raise SystemExit("A native Linux process is required for this evidence.")
    root = Path(__file__).resolve().parents[1]
    inputs = output / "input"
    inputs.mkdir()
    for name in ("all-four.toml", "profile.json", "facts.json", "x-catalog-2026-10-22.json",
                 "x-observations-2026-10-22.json"):
        shutil.copyfile(root / "examples/headless" / name, inputs / name)
    report["inputs_sha256"] = hashes(inputs)
    report["ollama_version"] = ollama("/api/version")
    available = ollama("/api/tags")
    report["installed_models"] = [{k: m.get(k) for k in ("name", "digest", "size", "details")}
                                  for m in available.get("models", [])]
    assert any(m["name"] == report["model"] for m in report["installed_models"])
    env = {k: v for k, v in os.environ.items() if not k.startswith("PATCHPITCH_") and k != "PYTHONPATH"}
    env.update(PATCHPITCH_MODEL=report["model"], PATCHPITCH_TIMEOUT="600", PATCHPITCH_SENTRY_DSN="",
               PYTHONUTF8="1")
    run = output / "campaign"
    with tempfile.TemporaryDirectory(prefix="patchpitch-linux-outside-") as outside:
        probe = subprocess.run([sys.executable, "-c",
            "import json,sys,patchpitch,patchpitch.campaigns; print(json.dumps({'package':patchpitch.__file__,"
            "'version':patchpitch.__version__,'ui_imported':any(m in sys.modules for m in ['fastapi','uvicorn','playwright'])}))"],
            cwd=outside, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        probe.check_returncode()
        report["installed_package"] = json.loads(probe.stdout)
        assert not report["installed_package"]["ui_imported"]
        assert not Path(report["installed_package"]["package"]).is_relative_to(root / "patchpitch")

        def cli(name, arguments):
            start = time.monotonic()
            result = subprocess.run([sys.executable, "-m", "patchpitch", *arguments, "--json"],
                cwd=outside, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                timeout=3600)
            (output / (name + ".stdout.json")).write_text(result.stdout, encoding="utf-8")
            (output / (name + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
            return {"exit_code": result.returncode, "elapsed_seconds": round(time.monotonic() - start, 3),
                    "summary": json.loads(result.stdout)}

        arguments = ["run", "--job", str(inputs / "all-four.toml"), "--out", str(run)]
        report["plan"] = cli("plan", arguments + ["--plan"])
        save(output / "report.json", report)
        if report["plan"]["exit_code"]:
            report["status"] = "invalid_plan"
            save(output / "report.json", report)
            return 1
        report["run"] = cli("run", arguments)
        save(output / "report.json", report)
        report["validation"] = cli("validation", ["validate", "--run", str(run)])
        if report["run"]["exit_code"] == 0:
            report["session_export"] = cli("export", ["export", "--run", str(run), "--kind", "session",
                                                       "--out", str(run / "session.json")])
            before = hashes(run)
            report["repeat"] = cli("repeat", arguments)
            report["resume"] = cli("resume", ["resume", "--run", str(run)])
            report["repeat_preserved_files"] = hashes(run) == before
            report["session_sha256"] = before.get("session.json")
    originals = []
    for p in sorted((run / "outputs").glob("*/original.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        originals.append({"target": p.parent.name, "mode": data["meta"]["mode"],
            "returned_model": data["meta"].get("returned_model"),
            "elapsed_seconds": data["meta"]["elapsed_seconds"]})
    report["original_results"] = originals
    assert all(r["mode"] == "LIVE_MODEL" for r in originals)
    report["status"] = "succeeded" if (report["run"]["exit_code"] == 0 and
        report["validation"]["exit_code"] == 0 and report.get("repeat_preserved_files") and
        report.get("session_export", {}).get("exit_code") == 0 and
        report.get("repeat", {}).get("exit_code") == 0 and report.get("resume", {}).get("exit_code") == 0 and
        len(originals) == 4) else "acceptance_failed"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    save(output / "report.json", report)
    save(output / "evidence-sha256.json", hashes(output))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
