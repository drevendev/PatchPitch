# PatchPitch

**Your product deserves a great story.**

Turn selected changelog facts into an announcement people understand. Describe
your product and audience, choose what shipped, generate with local Gemma, inspect
the sources, edit and export Markdown. A small writing workflow with a human final edit.

[Recorded demo](https://drevendev.github.io/PatchPitch/) ·
[63-second video](https://drevendev.github.io/PatchPitch/assets/demo.mp4) ·
[Build story on DEV](https://dev.to/drevendev/patchpitch-your-product-deserves-a-great-story-nao)

The hosted demo shows real recorded Gemma outputs; generation runs locally using
the setup below.

## Try it

**No install:** open the [recorded demo](https://drevendev.github.io/PatchPitch/).

**Locally, without a model.** You need Python 3.11+ (tested with 3.12) and Git.
Ollama isn't needed to look around:

```bash
git clone https://github.com/drevendev/PatchPitch.git
cd PatchPitch
python -m venv .venv
```

On Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn patchpitch.app:app --host 127.0.0.1 --port 8000
```

On Linux or macOS:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn patchpitch.app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Under **Reviewed fact packs**, pick one and click
**Load facts**. The app answers "Facts loaded. Review the selected notes before
generating." Loading a fact pack never runs a model. Without Ollama, **Write the
announcement** stops with "Ollama is not reachable at 127.0.0.1:11434. Start Ollama
and try again." Your input stays in place.

## Generate with local Gemma

Install [Ollama](https://ollama.com/), pull the model and start Ollama, then write
the announcement again:

```bash
ollama pull gemma4:12b
```

Tested on Windows 11 with Python 3.12.14 and Ollama 0.40.6. The source is
[MIT licensed](LICENSE).

The upstream is fixed to `127.0.0.1:11434`. Set `PATCHPITCH_MODEL` to an explicitly
installed model and `PATCHPITCH_TIMEOUT` to a timeout in seconds (default 420,
maximum 600). `.env.example` documents process settings; the app does not read
`.env` files automatically. No hosted inference key or paid fallback.

The current patch-based Idle Fantasy Shop example uses `gemma4:12b` with direct
generation (`think=False`) for all three formats, using temperature 1, top_p 0.95,
top_k 64. It needs more memory than a small 4B model. Earlier Gemma 3 runs and their
limitations are retained in the local evidence. A different model can be selected
through `PATCHPITCH_MODEL`; a valid schema does not guarantee equal writing quality.

A Russian walkthrough and validation record is available in
[Сессии и DevLog из Git](docs/sessions-git-devlogs.md).

## Next release specification

The [0.3.0 specification](docs/0.3.0-spec.md) sets the next release priorities:
Telegram, Twitter/X, DEV and GitHub; unattended CLI runs; exactly six evidence-backed
hashtags per X post; integrated Quillgrain profiles; and preparing the release's
own DEV article through PatchPitch. It defines planned behavior and acceptance
criteria. The implementation is in development as `0.3.0.dev0`.

## Run campaigns without UI

Install this checkout with `python -m pip install .`, prepare local Ollama with
your chosen model, then run the CLI without starting the web server:

```text
python -m patchpitch run --job examples/headless/campaign.toml --out-root artifacts/campaigns --plan --json
python -m patchpitch run --job examples/headless/campaign.toml --out-root artifacts/campaigns --json
```

The CLI accepts JSON/TOML jobs, keeps attempts/checkpoints on disk, resumes failed
steps explicitly and preserves publication edits. `--out-root` chooses a stable
directory from the inputs so unchanged scheduled jobs reuse their result. CLI
dependencies do not require FastAPI or a browser; `pip install ".[ui]"` also
installs the studio server. New X campaigns require a dated observation catalog
for six relevant tags per post. Quillgrain can compile a selected local pack;
DEV draft delivery is a separate explicit command.

See [headless setup, scheduling, Git, tags, voice and exports](docs/headless.md).
The [four-platform example](examples/headless/all-four.toml) includes an
[observed X catalog and sampling notes](docs/x-catalog.md).
The sample prepares development drafts; it does not announce a published release.

## Optional author voice and Russian Telegram

Load a local Quillgrain `voice-bundle.json`, choose Russian / Telegram and write
with the selected author context instead of a generic tone preset. Session files
preserve the exact voice snapshot and your edits. The engine is optional; see
[setup, import and limitations](docs/quillgrain-voice.md). This is a local working
implementation, not a published new release or proof of stylistic fidelity.


## What's new in 0.2.0 (review candidate)

**X Single** and **X Thread** formats, **Reviewed fact packs** with provenance, and
per-card editing, reordering and regeneration. See the
[Social Field Test details](docs/social-field-test.md) and the
[review record and release gates](docs/0.2.0-review.md). The real X composer check
was deferred and has not passed.

## Save and open local work

Open **Save and open**. **Download session** saves a versioned JSON file with the
current input and fact selection, source snapshots, every format's current edits,
X order/media notes, original generation records, unfinished Git review (selected
files, diff snapshots and edited fact candidates) and manual publication markers.
**Open session JSON** validates the entire file before replacing this tab, asks
before replacing nonempty work, restores exact text and does not run inference.
The restored selection requires review before another generation.

**Download product profile** contains only product name/description, audience and
CTA. Applying a profile keeps release notes and existing drafts, clears the
release-specific media brief and requires a new context review. Profiles do not
carry old release facts into a new release.

Files are explicit and local; there is no autosave, browser database or cloud
sync. A session can contain private source text, local repository controls and
model responses: keep it private. Save files are limited to 32 MB, 100 current
format variants and 200 generation records. Invalid/version-mismatched files do
not replace the current work. A standalone Generation record JSON is diagnostic
evidence, not a session file.
The actual formatted JSON download is checked before saving: an over-budget
session stays in the tab, with a clear error instead of an unusable save file.

Rejected inputs (including HTTP 422 attempts) remain saveable as original failure
records. The replacement/unload guard also covers unfinished Git-only reviews;
the browser warning is best effort and does not save work automatically.

## Write a DevLog from recent commits

1. Open **DevLog from Git** and enter a **local repository root**. Choose recent
   commits (1–30), an explicit base/head range, or a saved manual-publication
   baseline. An optional repository-relative path prefix narrows the file scope.
2. Click **Inspect Git range**. Inspect exact resolved SHA values, commit subjects,
   dirty-tree disclosure and every omitted file. Recent mode finds a first-parent
   baseline; the resulting range includes merged commits, with facts based on the
   net diff rather than duplicate merge subjects. Uncommitted edits are excluded.
3. Explicitly select eligible files and click **Review selected diffs**. Read the
   displayed patches and confirm you may use them. No model call has occurred.
4. Review the displayed parts and request count, then click **Suggest facts with
   local Gemma**. Large diffs are split without clipping and processed in bounded,
   sequential requests. Progress is visible. **Stop after current request** keeps
   completed batches; a failed batch is never retried automatically. Download the
   session to continue later with **Continue remaining batches**, after confirming
   the restored diffs. Earlier candidate edits and original responses stay intact.
   Re-inspecting the same committed selection restores those edits and choices,
   even after Save/Open while the visible diff preview is invalidated.
   Inspect cited parts, remove duplicate/uncertain claims and explicitly select
   up to 15 facts. Commit subjects and model labels do not prove behavior or tests.
5. Click **Use selected facts for DevLog**. Review the product/audience and chosen
   notes in the normal editor, confirm the selection, then write a Devlog. This
   is a separate explicit model request. Git inputs use **Development progress**:
   committed code is not automatically called released, deployed or available.
6. Edit, inspect sources, download the session and export Markdown. Publish in
   DEV, itch.io, X or another editor **manually**.
7. Only after actual publication, use **Record a manual publication** for the
   displayed Git draft with its real URL. Download the session to retain this
   repository's published head. Generation, export and failures never advance
   that marker. The next import can use **Since recorded manual publication**.

For PatchPitch itself, a useful reproducible range is `f5baf58..6f84004` with
`patchpitch/generator.py`, `patchpitch/static/generation-records.js` and
`patchpitch/static/social-editor.js` selected. It describes generation records on
main, not a new public Release. The historical hand-prepared Idle Fantasy Shop
fixture remains available as a separate input.

The first importer supports local SHA-1 repositories, ancestor ranges of at most
50 commits and at most 200 changed paths. Choose at most 12 text files, 128 KB of
diff per file and 192 KB total. Fragments are at most 6 KB; model batches are at
most 12 KB of serialized evidence, with at most 64 parts and 24 requests per
review. Exact UTF-8 bytes are preserved, including long lines. Fragment labels
show file, part and byte range; continuing hunks remain explicitly partial.
Git extraction reserves a 24,576-token context for dense code and model output.
All parts must finish before applying candidates to a DevLog. Only the selected
1–15 facts (at most 6,000 characters) go to the writer; the full candidate pool
and processing checkpoints stay in the session. Oversized inputs fail before inference; omitted
binary/generated/dependency/sensitive filenames are disclosed. Symlinks,
submodules and non-UTF-8 inputs are unsupported. A filename/credential check is
an aid, not a guarantee: inspect the selected code for private material yourself.
The full selected review and original model response can be downloaded with
**Download Git review JSON**; the current session also retains the last import
record, including accepted/failed batch attempts. Older session files remain
openable. A restored review keeps candidate edits and selection, while requiring
a new explicit diff confirmation before another extraction. Nothing is
posted or sent to a hosted model.

Git is invoked with fixed argument lists, bounded output/time and external diff,
textconv, hooks and filesystem monitoring disabled. The importer does not change
checkout, run project code/builds, fetch, clone or push. A partial selection is
marked partial; facts from unselected files never enter the extraction request.

## From facts to a final edit

1. Add the product, audience and 1–15 short change notes (6,000 characters total).
2. Review Include checkboxes. Planned, internal, blocked, unknown and Unreleased
   notes start excluded. Confirm what belongs in the announcement.
3. Choose a **format**, **style** and optional **Auto tags**, then click
   **Write the announcement**. Ordinary formats make one local model request.
   The new six-tag X workflow first plans topics, then writes the selected plan;
   both original responses are retained. It makes at most two requests.
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
switch between them. Download a session before refresh to restore them later. A new request locks the
editor until success or failure; failure keeps the previous draft and edits.
Generating over an edited draft of the same format requires confirmation.

**Generation records** keeps each attempted generation or single-card rewrite in
this tab, including failures. Select an attempt to inspect its original model
response and the reason it was rejected. A failure leaves the input and existing
draft edits intact; retry is always an explicit action. A later success keeps the
earlier failure available. A timeout without a response shows that no response is
available and does not invent a returned model identity.

Use **Copy record JSON** or **Download record JSON** to save the input snapshot,
original response, error and model settings for review. Successful records also
include the current draft snapshot when that draft is still available. Original
API responses and manual edits stay separate; edited text is not automatically
revalidated. Records may contain private input and model text. They are not
automatically written to disk, browser storage or telemetry, and are lost when the
tab closes or refreshes unless included in an explicitly downloaded session.
The unload warning remains best effort.

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
summary of a real patch prepared before the new Git workflow; it is not a live
import of the game repository. The published devlog is
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
social integrations or publishing endpoints. Telemetry is off unless you explicitly
configure the optional Sentry DSN described below. Excluded facts and CTA
never enter the model payload; the server appends the supplied CTA. HTML is text.

## Optional Sentry diagnostics

Without `PATCHPITCH_SENTRY_DSN`, no SDK client is initialized and generation stays
local. To opt in, set the DSN in the process environment before starting the app:

```powershell
$env:PATCHPITCH_SENTRY_DSN = 'YOUR_PROJECT_DSN'
$env:PATCHPITCH_SENTRY_RELEASE = (git rev-parse HEAD)
.\.venv\Scripts\python.exe -m uvicorn patchpitch.app:app --host 127.0.0.1 --port 8000
```

The optional export contains a generation transaction, one span around the real
Ollama request and one around draft validation. It includes elapsed time, format,
requested/actually returned model, available input/output token counts and bounded
error codes. Missing token usage or returned identity stays absent. There is no
agent loop or estimated model cost. `/api/health` reports `sentry_enabled`; when
enabled, successful response metadata includes a locally generated trace ID.
An ID alone does not confirm that Sentry received it.

The pinned Python SDK uses manual instrumentation, with automatic integrations,
PII collection, local variables, source context, request bodies, logs, metrics,
sessions and profiling disabled. Completed transactions use the static transport
format so the same filter covers all spans. Both events and final transport
envelopes are rebuilt from a small allowlist. Drafts, notes, voice samples, prompt
messages, output text, user data, breadcrumbs, extras, attachments and sampling
baggage are excluded. Delivery failure leaves the generation result unchanged.

Sentry's server can derive location from the network connection even when no user
fields leave the SDK. In the project's **Security & Privacy** settings, enable
**Prevent Storing of IP Addresses** and add the advanced scrubbing rule
`[Remove] [Anything] from [$user.geo.**]`. These settings affect new events only;
verify the received event as well as the outgoing packet. See Sentry's
[server-side scrubbing documentation](https://docs.sentry.io/security-legal-pii/scrubbing/server-side-scrubbing/#geographic-information).

Use an existing free Sentry project with paid overages disabled. No account,
project, paid subscription or API token is created by the app. The DSN is a local
configuration value and must not be committed. See Sentry's
[manual AI instrumentation](https://docs.sentry.io/platforms/python/agent-tracing/manual-instrumentation/)
and [data collection documentation](https://docs.sentry.io/platforms/python/data-management/data-collected/).

`scripts/sentry_check.py --offline --output artifacts/sentry-offline-check` audits
serialized transport with a deliberately invalid public fixture and no network.
`--live` instead performs one real generation on the public fictional Pocket
Orchard example, then a separate `CONTROLLED_FAILURE` validation check. It requires
your DSN and Ollama. It retains local IDs and payloads for review; it does not
claim remote acceptance or publish evidence automatically.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-dev.lock
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.tools\browsers'
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
```

The development lock records a tested Python 3.12 dependency snapshot. CI installs
both the direct requirements and this snapshot so incompatible pins fail during
installation. To refresh it, install `requirements-dev.txt` in a fresh virtual
environment and record `python -m pip freeze`.

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

To start a workspace prepared by `scripts/bootstrap_local.py`:

```powershell
$env:PATCHPITCH_MODEL = 'gemma4:12b'
$env:PATCHPITCH_SENTRY_DSN = ''
.\scripts\start_local.ps1
```

Open **http://127.0.0.1:8000**. Keep this PowerShell process running; Ctrl+C stops
the app. The launcher can start the existing workspace Ollama if it is not already
running. No download happens in this startup path.

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

Private handoff files and local evaluation evidence stay excluded from Git.
The previously approved article, demo video and supporting assets are intentionally
published from `public-demo/`. This repository also contains implementation,
examples, tests and reproduction scripts. The 0.2.0 source candidate includes
approved edited examples staged for a future Pages update. Full raw evidence
remains private; Release, Pages deployment, X and DEV publication are separate
owner decisions. See [REUSE.md](REUSE.md) and
[third-party notices](THIRD_PARTY_NOTICES.md) for provenance.

This new project began 2026-10-18. Any source changes after the challenge cutoff
(2026-10-19 09:59 Asia/Nicosia) must be disclosed here. The 0.2.0 Social Field Test
implementation, tests, fact packs and publication/provenance documentation changes
were prepared on 2026-10-20 after that cutoff; they are not part of the contest build.


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

Publication follow-up: [23 October article closeout](docs/publication-closeout-2026-10-23.md).
Deferred work: [project backlog](docs/backlog.md).
