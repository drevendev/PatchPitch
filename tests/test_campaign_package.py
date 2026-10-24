"""Install the actual package and invoke it with stdin closed outside the repo."""
import json
import os
import subprocess
import sys
from pathlib import Path

from test_campaigns import job_files


def test_installed_package_has_no_ui_dependency_and_plans_outside_checkout(job_files, tmp_path):
    job, out, _ = job_files
    root = Path(__file__).resolve().parents[1]
    installed = tmp_path / "installed"
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation",
                    "--target", str(installed), str(root)], check=True, capture_output=True, text=True)
    external = tmp_path / "outside"
    external.mkdir()
    env = {**os.environ, "PYTHONPATH": str(installed)}
    result = subprocess.run([sys.executable, "-m", "patchpitch", "run", "--job", str(job), "--out", str(out), "--plan", "--json"],
                            cwd=external, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "planned"
    probe = subprocess.run([sys.executable, "-c", "import patchpitch.campaigns,sys; assert 'fastapi' not in sys.modules; print(patchpitch.campaigns.__file__)"],
                           cwd=external, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert probe.returncode == 0 and str(installed) in probe.stdout
    assert (installed / "patchpitch/prompts/telegram-author-ru.txt").exists()
