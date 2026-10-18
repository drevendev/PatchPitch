"""Workspace-only free tooling setup. No system install, paid APIs or publication."""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"


def main():
    (ROOT / "submission").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(parents=True, exist_ok=True)
    TOOLS.mkdir(exist_ok=True)
    request = urllib.request.Request("https://api.github.com/repos/ollama/ollama/releases/latest", headers={"User-Agent": "PatchPitch-local-setup"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    asset = next(a for a in release["assets"] if a["name"] == "ollama-windows-amd64.zip")
    archive = TOOLS / asset["name"]
    executable = TOOLS / "ollama" / "ollama.exe"
    if not executable.exists():
        if not archive.exists() or archive.stat().st_size != asset["size"]:
            print(f"Downloading free portable Ollama {release['tag_name']}: {asset['size'] / 1e9:.2f} GB", flush=True)
            with urllib.request.urlopen(asset["browser_download_url"], timeout=90) as response, archive.open("wb") as output:
                count = 0
                while chunk := response.read(8 * 1024 * 1024):
                    output.write(chunk)
                    count += len(chunk)
                    if count % (128 * 1024 * 1024) == 0:
                        print(f"Downloaded {count / 1e9:.2f} GB", flush=True)
        digest = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
        expected = asset.get("digest", "")
        if expected and expected != "sha256:" + digest:
            raise RuntimeError("Official asset checksum mismatch")
        print("Extracting portable runtime…", flush=True)
        with zipfile.ZipFile(archive) as package:
            # Only an official fixed-name package, with paths bounded to its directory.
            target = (TOOLS / "ollama").resolve()
            for name in package.namelist():
                if not (target / name).resolve().is_relative_to(target):
                    raise RuntimeError("Unsafe archive path")
            package.extractall(target)
        (TOOLS / "ollama-install.json").write_text(json.dumps({"version": release["tag_name"], "url": asset["browser_download_url"], "sha256": digest, "official_digest": expected}, indent=2), encoding="utf-8")
    env = os.environ.copy()
    env.update({"OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_MODELS": str(TOOLS / "models"), "OLLAMA_NO_CLOUD": "1", "USERPROFILE": str(TOOLS / "runtime-home")})
    (TOOLS / "runtime-home").mkdir(exist_ok=True)
    output = (ROOT / "artifacts" / "ollama.log").open("a", encoding="utf-8")
    process = subprocess.Popen([str(executable), "serve"], env=env, stdout=output, stderr=output, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    (TOOLS / "ollama.pid").write_text(str(process.pid))
    print(f"Ollama PID {process.pid}; loopback only. Run .tools/ollama/ollama.exe pull gemma4:12b next.", flush=True)


if __name__ == "__main__":
    main()
