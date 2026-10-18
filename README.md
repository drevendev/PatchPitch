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
ollama pull gemma4:12b
.\.venv\Scripts\python.exe -m uvicorn patchpitch.app:app --host 127.0.0.1 --port 8000
```

Start Ollama, then open **http://127.0.0.1:8000**. On Linux/macOS use
`.venv/bin/python` in place of `.venv\Scripts\python.exe`.

The upstream is fixed to `127.0.0.1:11434`. Set `PATCHPITCH_MODEL` to an explicitly
installed model and `PATCHPITCH_TIMEOUT` to a timeout in seconds (default 420,
maximum 600). `.env.example` documents process settings; the app does not read
`.env` files automatically. No hosted inference key or paid fallback.

The current patch-based Idle Fantasy Shop example uses `gemma4:12b` with thinking
enabled for full devlogs and direct responses for social posts, with the model
author's sampling profile: temperature 1, top_p 0.95,
top_k 64. It needs more memory than a small 4B model. Earlier Gemma 3 runs and their
limitations are retained in the local evidence. A different model can be selected
through `PATCHPITCH_MODEL`; a valid schema does not guarantee equal writing quality.

## From facts to a final edit

1. Add the product, audience and 1–15 short change notes (6,000 characters total).
2. Review Include checkboxes. Planned, internal, blocked, unknown and Unreleased
   notes start excluded. Confirm what belongs in the announcement.
3. Choose a **format**, **style** and optional **Auto tags**, then click
   **Write the announcement**. One click makes one local model request.
4. Read the draft and **Source notes**. The original facts stay visible for inspection.
5. Review the result, remove unwanted tag chips, then **Edit draft**,
   **Copy Markdown** or **Download Markdown**.

Formats share the same selected facts, but have different editorial jobs:

| Format | Result |
| --- | --- |
| Devlog | Title, introduction, all selected topics and any explicit important note. |
| Community post | Connected prose focused on a few useful changes; up to 1,600 Unicode characters. |
| Short post | One concrete thought; up to 280 Unicode characters, including the exact CTA, separators and hashtags. |

Short formats show which selected source IDs were not referenced. This is not a
claim that every detail within a cited note survived. Review prerequisites,
exceptions and backup guidance. If a model exceeds the limit, the request fails
clearly; the application neither truncates the output nor silently retries.
The short-post counter is a general Unicode character budget, not a platform API
validator (services may weight URLs or characters differently).

**Warm**, **Clear** and **Lively** are bounded writing presets. Your optional
voice sample still provides rhythm and character, never factual support. Auto
tags are off by default: Gemma can choose up to three suggestions (one for a
short post) from a small
vocabulary derived from the product context and included facts. No trend/reach
lookup or invented platform-support tags. Remove suggestions with their chips,
or edit/add your own tags in Markdown.

The latest generated draft for each format stays in this browser tab's memory,
including manual edits and tag removals. Use the generated-format buttons to
switch between them. Refreshing the page clears them. A new request locks the
editor until success or failure; failure keeps the previous draft and edits.
Generating over an edited draft of the same format requires confirmation.

An optional writing sample helps retain the maker's voice. The first three selected
notes lead the announcement; remaining topics appear in a compact secondary section.
Technical notes are split into factual units for the model's context. Gemma writes
whole paragraphs, a title and an introduction in one response. The schema constrains
structure and citations without supplying any announcement sentences. It is shown
to the model as well as passed to Ollama's format control. The response is exported
without editorial rewriting or automatic prose cleanup; the raw structured response
remains available. These checks do not establish semantic truth: the maker must
still review the wording against the facts.

The compact studio bundles OFL-licensed Manrope and Newsreader locally. Fact cards
use short titles and switches; expand a card to read its original note. Secondary
changes and sources are folded on the main desktop screen and fully included in
Markdown. Mobile uses normal vertical page flow. See THIRD_PARTY_NOTICES.md.

**Try an example** loads technical notes prepared from the owner's actual Idle
Fantasy Shop 0.11.1 → 0.12 code patch (`e83ddda` → `c4389af`), with an internal
delivery note excluded. File references are recorded in
`examples/idle-fantasy-shop.provenance.json`. This is a human-prepared factual
summary of a real patch, not an automatic Git importer. The published devlog is
used only for comparison; none of its prose enters this case. A short tone brief comes from the game’s in-game item descriptions, with separate provenance.
It loads input, then asks you to run real generation.
Other examples are labelled public documentation or fictional products.

Source IDs check that a citation exists; they do **not** prove a sentence is true.
A small model can still change a quantity or overstate a feature. Links and
numbers absent from the input trigger review warnings, including common number
words. Every output stays **Draft — review before publishing**. After editing,
links still refer to the original generated draft. Export uses your current text.
Explicit backup/compatibility instructions require a source-linked note; a
missing note is an error. Unreferenced selected facts also trigger a warning.
These are inspection checks, not semantic verification.

Input and draft variants are not persisted automatically. There are no accounts, database,
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
  raw video and evidence hashes. No mocked network transport. Default capture
  exports the automatic draft without editorial changes; `--edit-file` is explicit.
- `scripts/render_video.py`: local FFmpeg/ffprobe, 63-second H.264 video and captions.
- `scripts/narrate_kokoro.py`: optional local Kokoro neural narration.
  Install `requirements-audio.txt`; Apache-2.0 model/voice files remain in `.tools/`.
- `scripts/build_sample.py`: visibly recorded SAMPLE page with no inference or
  requests to a visitor's localhost.

Each producer creates its own ignored output directories, including on a clean
checkout. Install development/browser dependencies first. The demo tools consume
earlier results in this order: **capture → render → build sample**. For neural
audio: render once to prepare narration cues, run `narrate_kokoro.py` and
`compose_music.py`, then render with the desired audio options. A missing input
artifact remains an error; directory creation does not fabricate evidence.

`doctor.py` without `--live` records `LIVE_MODEL: NOT_RUN`, even if Ollama is
unavailable. `evaluate.py --live` first checks the running app against the
evaluator's model, digest and options; mismatches stop before inference.
Each attempt has a fresh directory under `artifacts/evaluation/`. Raw response
identity and configuration evidence are separate from pending human quality
review. Earlier tuned or differently configured attempts remain historical,
not a controlled same-model benchmark.

FFmpeg and ffprobe must be on PATH, or under `.tools/ffmpeg/**/bin/` on Windows.
`python scripts/render_video.py --voice kokoro` uses local neural narration;
`--voice none --music none` renders captions only. Original local procedural
  music, fixed UI framing, quiet editorial accents and soft scene transitions are optional demo tooling. The older Windows voice is an explicit
fallback. No paid voice API, music or voice cloning is used.

The article, videos, handoff and local evidence stay excluded from Git. Publishing
source code does not publish those materials. This repository contains implementation,
examples, tests and reproduction scripts. See [REUSE.md](REUSE.md) and
[third-party notices](THIRD_PARTY_NOTICES.md) for provenance.

This new project began 2026-10-18. Any source changes after the challenge cutoff
(2026-10-19 09:59 Asia/Nicosia) must be disclosed here; none are currently recorded.


The current studio uses smooth, reversible disclosures and expandable previews for
long highlights. Copy/Download always include every original model word. Reduced
motion is respected. During video capture, use viewport screenshots only: a full-page
screenshot can temporarily resize Chromium's recording surface and leave gray frames.

After a real `scripts/capture_demo.py` take, optional `scripts/record_review.py`
replays that exact saved model response only for clearer source review/export footage.
It performs no new inference and records this explicitly. Use
`python scripts/render_video.py --reuse-voice --review-replay` to label those passages.
`python scripts/verify_motion.py` decodes the footage and checks the reproduced gray
resize defect; it is not a general visual-quality guarantee.

`python scripts/verify_audio.py` checks decoded audio for clipping, a surviving
closing music tail, fade to silence and room after the last spoken line. It does
not substitute for listening to the finished demo.
