# PatchPitch

**Your product deserves a great story.**

Turn selected changelog facts into an announcement people understand. Describe
your product and audience, choose what shipped, generate with local Gemma, inspect
the sources, edit and export Markdown. A small writing workflow with a human final edit.

## Run locally

Python 3.11+ and [Ollama](https://ollama.com/) are required. Tested on Windows 11
with Python 3.12.14 and Ollama 0.40.6. The source is [MIT licensed](LICENSE).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull gemma3:4b
.\.venv\Scripts\python.exe -m uvicorn patchpitch.app:app --host 127.0.0.1 --port 8000
```

Start Ollama, then open **http://127.0.0.1:8000**. On Linux/macOS use
`.venv/bin/python` in place of `.venv\Scripts\python.exe`.

The upstream is fixed to `127.0.0.1:11434`. Set `PATCHPITCH_MODEL` to an explicitly
installed model and `PATCHPITCH_TIMEOUT` to a timeout in seconds (default 180,
maximum 600). `.env.example` documents process settings; the app does not read
`.env` files automatically. No hosted inference key or paid fallback.

## From facts to a final edit

1. Add the product, audience and 1–15 short change notes (6,000 characters total).
2. Review Include checkboxes. Planned, internal, blocked, unknown and Unreleased
   notes start excluded. Confirm what belongs in the announcement.
3. Click **Write the announcement**. One click makes one local model request.
4. Read the draft and **Source notes**. The original facts stay visible for inspection.
5. **Edit draft**, **Copy Markdown** or **Download Markdown**.

**Try an example** loads real, selected facts from the owner's
[Idle Fantasy Shop 0.12 devlog](https://drevengames.itch.io/idle-fantasy-shop/devlog/1714671/title-012-plan-a-little-let-the-fields-rest),
with a future plan excluded. It loads input, then asks you to run real generation.
Other examples are labelled public documentation or fictional products.

Source IDs check that a citation exists; they do **not** prove a sentence is true.
A small model can still change a quantity or overstate a feature. Links and
numbers absent from the input trigger review warnings, including common number
words. Every output stays **Draft — review before publishing**. After editing,
links still refer to the original generated draft. Export uses your current text.

Input and history are not saved automatically. There are no accounts, database,
social integrations, publishing endpoints or telemetry. Excluded facts and CTA
never enter the model payload; the server appends the supplied CTA. HTML is text.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.tools\browsers'
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
```

Linux CI installs Chromium with `python -m playwright install --with-deps chromium`.
Unit/API/browser tests use explicitly labelled **MOCK** responses. Real inference
is a separate opt-in check with `scripts/doctor.py --live` and
`scripts/evaluate.py --live`; it needs your own running Ollama. No model download
is part of GitHub Actions. The workflow uses a standard public Linux runner and
skips private repositories.

## Optional local demo tooling

The Python application has no Node, React, ORM, Docker or runtime video features.
The following scripts are development tools, not product features:

- `scripts/bootstrap_local.py`: free Windows portable Ollama under `.tools/`,
  loopback only, project-local models/profile, cloud disabled. Several GB download.
- `scripts/start_local.ps1`: start that prepared local workspace.
- `scripts/capture_demo.py`: real browser → model → sources → edit → clipboard/export,
  raw video and evidence hashes. No mocked network transport.
- `scripts/render_video.py`: local FFmpeg/ffprobe, 63-second H.264 video and captions.
- `scripts/narrate_kokoro.py`: optional local Kokoro neural narration.
  Install `requirements-audio.txt`; Apache-2.0 model/voice files remain in `.tools/`.
- `scripts/build_sample.py`: visibly recorded SAMPLE page with no inference or
  requests to a visitor's localhost.

FFmpeg and ffprobe must be on PATH, or under `.tools/ffmpeg/**/bin/` on Windows.
`python scripts/render_video.py --voice kokoro` uses local neural narration;
`--voice none` renders captions only. The older Windows voice is an explicit
fallback. No paid voice API, music or voice cloning is used.

The article, videos, handoff and local evidence stay excluded from Git. Publishing
source code does not publish those materials. This repository contains implementation,
examples, tests and reproduction scripts. See [REUSE.md](REUSE.md) and
[third-party notices](THIRD_PARTY_NOTICES.md) for provenance.

This new project began 2026-10-18. Any source changes after the challenge cutoff
(2026-10-19 09:59 Asia/Nicosia) must be disclosed here; none are currently recorded.
