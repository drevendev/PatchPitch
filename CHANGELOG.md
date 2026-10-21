# PatchPitch local development log

## 2026-10-21 — 0.2.0 stabilization (owner review pending)

- Retain original accepted and rejected responses in Devlog, Community and Short,
  matching X diagnostics; include input snapshots on successful legacy responses.
- Add session-only Generation records for all formats and single-card rewrites,
  with reasons, model identity, explicit JSON Copy/Download and separate edited
  snapshots. A later success retains earlier failed attempts.
- Preserve the current input and edited draft on rejection; no automatic retry,
  truncation, repair or filesystem/browser-storage persistence.
- Add regressions for all five formats, overflow, malformed/incomplete output,
  transport failure, safe response display, retry, exports and telemetry privacy.
- PR review correction: associate each regenerated card with its generation record
  so JSON export includes its current edits and media notes. A later rewrite of
  that card no longer supplies a snapshot to the superseded record.
- PR #44 was merged on 2026-10-20; post-merge CI passed 177 tests. This follow-up
  remains separate from Release, Pages, X and DEV publication.

## 2026-10-20 — 0.2.0 Social Field Test candidate (PR review)

- Added versioned PatchPitch/Idle Fantasy Shop fact packs, strict JSON import,
  source provenance mapping and explicit selection confirmation (#30).
- Added X Single and 3–7-card X Thread, writing goals, source inspection,
  edits, reordering and explicit single-card regeneration (#35).
- Preserved drafts across products/releases/formats; protected other card edits
  on failure and retained raw rejected responses as local diagnostic evidence.
- Added shared conservative X length estimates, explicit X-preview requirement,
  per-post plaintext Copy and exact current-thread Markdown downloads.
- Distinguished configured/returned model identity and missing usage (#41).
- Added best-effort unload warnings (#42) and safe contextual filenames (#43).
- Corrected approved-public/private media provenance and disclosed this work as
  post-challenge development (#28). Existing published assets are unchanged.
- Added offline API/browser/privacy regressions and an opt-in three-case real
  browser/Gemma pilot. Owner acceptance and publication remain separate gates.
- Recorded owner acceptance of the three edited texts and the application;
  real X composer preview is deferred by the owner and has not passed.
- Staged a version-labelled Pages example page for review, preserving the
  accepted historical article and recording. Deployment remains manual.

The owner subsequently authorized merging PR #44; it is on main. No GitHub Release/tag,
Pages deployment or social publication followed. Full sessions (#11), feedback (#36/#37),
Git import and a hosted live model remain later work.

## 2026-10-19 — formats, styles and auto tags

- Added devlog, community and 280-character short-post formats with Warm, Clear
  and Lively styles. Short outputs disclose unreferenced selected sources.
- Added optional source-based hashtag suggestions, removable before export.
- Kept generated formats and their edits in tab memory, with exact Markdown export.
- Fixed nested Unreleased exclusion (#1) and locked output editing during requests (#2).
- Prepared ignored output parents before evidence tooling runs (#3), retained
  distinct evaluation attempts, and checked actual model configuration for comparisons (#4).
- Deferred translation, product video generation and commit import to backlog #6–#8.

Source publication is owner-approved. The article, generated video and local
evidence remain excluded from Git and unpublished. This is not a package release.

## 2026-10-18 — v0.1 working local demo (unpublished)

- Built the local product/audience/selected-change workflow with one Gemma request.
- Added strict structured drafts, source-note inspection, human edits and Markdown export.
- Added explicit local-model errors, bounded input and safe text rendering.
- Ran 30 unit/API/MOCK browser tests and real local Gemma flows.
- Prepared real Playwright capture, FFmpeg editing and an unpublished DEV article.

This records local implementation, not a public package release or independent acceptance.

## 2026-10-18 — owner-approved public source and demo refinement

- Applied MIT and published the source to `drevendev/PatchPitch`; article/video remain local.
- Exercised GitHub Actions on a standard public Linux runner.
- Added the real Idle Fantasy Shop 0.12 example and balanced editorial typography.
- Fixed Gemma's consecutive-user-turn prompt handling and bounded source-ID schema.
- Added review warnings for spelled-out numbers/uncited facts and a required note for explicit backup instructions.
- Added optional local Kokoro narration, with no speech stretching or packet-copy joins.

## 2026-10-18 — local studio and generation iteration (not published)

- Added the maker's optional voice reference, full source topics and a secondary section.
- Preserved explicit limits and exceptions in constant source-sentence fields, with local checks.
- Kept raw output and conservative automatic duplicate-removal records; blocked invented notes.
- Reworked the compact green/paper studio with bundled OFL fonts and expandable fact cards.
- Fixed the stale-server example error and enabled reload in the local launcher.
- Added warm game-focused narration, original background music, eased motion and smooth transitions.

These source changes are included in the repository update of 2026-10-19.
Their generated media remain local and unpublished.

## 2026-10-18 — independent patch input (local, not published)

- Replaced devlog-derived example prose with technical facts from the actual
  Idle Fantasy Shop 0.11.1 → 0.12 diff, with commit and file provenance.
- Kept the original devlog for comparison only; the tone brief comes from in-game text.
- Removed fixed announcement sentences and automatic prose cleanup from generation.
- Showed the output schema to Gemma as context and rejected unfinished paragraphs.
- Evaluated local Gemma 4 as well as Gemma 3; kept unsuccessful attempts and raw responses.

- Replaced camera zoom/pan with fixed UI framing, quiet accents and soft scene reveals.
- Added a PatchPitch-focused closing line, brand hold, final musical cadence and fade to silence.
- Reproduced and removed the gray recording band caused by full-page screenshots during capture.
- Added reversible disclosure animations, keyboard/reduced-motion coverage and full-text-preserving previews.
- Source-review/export footage can explicitly replay the real saved draft; no additional inference is claimed.
