"""Read-only local environment check; --live explicitly runs one short Gemma call."""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from patchpitch import generator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "os": platform.platform(), "python": sys.version, "git": shutil.which("git"), "LIVE_MODEL": "NOT_RUN"}
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        result["ffmpeg"] = subprocess.check_output([ffmpeg, "-version"], text=True).splitlines()[0]
    except (ImportError, OSError) as exc:
        result["ffmpeg"] = "NOT_AVAILABLE"
    result["playwright_browsers"] = os.getenv("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".tools" / "browsers"))
    try:
        result["ollama"] = generator.ollama_json("/api/version")
        result["models"] = generator.ollama_json("/api/tags").get("models", [])
        if args.live:
            payload = {"model": generator.MODEL, "stream": False, "messages": [{"role":"user", "content":"Reply with exactly: PatchPitch ready"}], "options": {"temperature":0, "num_predict":32}}
            start = time.perf_counter()
            result["live_response"] = generator.ollama_json("/api/chat", payload, timeout=180)
            result["live_elapsed_seconds"] = round(time.perf_counter() - start, 3)
            result["LIVE_MODEL"] = "EXERCISED"
    except generator.GenerationError as exc:
        result["ollama_error"] = {"code":exc.code, "message":exc.message}
    target = ROOT / "submission" / "environment.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
