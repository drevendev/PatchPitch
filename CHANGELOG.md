# PatchPitch local development log

## Unreleased — 0.3.0.dev0 unattended campaigns

- Add an installable Python CLI for strict JSON/TOML jobs, shared local generation,
  persistent run/attempt files, explicit resume and nonblocking process locks.
- Preserve accepted responses across interruption/export gaps and keep publication
  edits on resume. Derive scheduled run directories from the full input digest.
- Support committed Git extraction without UI, disclose machine-selected facts,
  and bind saved candidate selections to source and candidate digests.
- Add evidence-backed six-tag X planning, deterministic catalog selection and
  full-post budget checks; validate manual exports in CLI and studio. Preserve
  explicit legacy X workflows and old session files.
- Include a dated public X observation ledger/catalog and a four-platform job.
  Constrain model prose to the space left by six tags and the final CTA.
- Compile chosen Quillgrain local packs or verify imported bundles with explicit
  language/register/channel. Preserve per-request voice snapshots and optional
  engine installation.
- Add DEV articles/GitHub notes, editable publication files and campaign-to-studio
  session export. Add explicit draft-only DEV delivery with receipts, ownership
  checks and unknown-outcome reconciliation.
- Reconcile uncertain DEV writes when the API omits AI disclosure, retaining the
  original outgoing payload and updating the same owned draft without duplicate POSTs.
- Add a pinned Quillgrain integration CI job that fails on skipped checks.
- Add offline automation/API/browser/package tests and scheduling examples.
  Real-model quality, remote DEV draft verification and release publication remain
  separate checks; no public Release or platform publication is implied.

## Unreleased — first-run documentation

- README starts with a first run that needs no model: the recorded demo, then a
  clean clone that loads a reviewed fact pack without Ollama and shows the exact
  message Generate gives while Ollama is stopped. Model setup follows.
- The 0.2.0 Social Field Test details and live-evidence steps moved, unchanged, to
  `docs/social-field-test.md`. The prepared-workspace launcher moved to the demo
  tooling section, and the Python requirement reads the same everywhere (3.11+).
- Add CONTRIBUTING.md and SECURITY.md (private vulnerability reporting).

## Unreleased — large Git diffs

- Split large committed diffs into lossless UTF-8 parts with file/part/byte
  citations; show the full review and model-request plan before extraction.
- Process bounded batches sequentially, retain original accepted/failed attempts,
  and support stopping and explicit continuation from saved session checkpoints.
- Keep candidate edits when continuing; require all parts to finish and explicit
  human selection of at most 15 facts before writing. Preserve older sessions.
- Raise Git read budgets to 128 KB per file and 192 KB total. The 6 KB cap now
  applies to fragments; each model request has at most 12 KB of serialized evidence.
- Retain candidate edits when re-inspecting the same diff, including Save/Open
  while the preview is invalidated; validate originals before reattaching edits.
- Allow session files up to 32 MB and check the actual formatted download size
  before Save, so large checkpoint histories remain openable.
- Publication remains manual.

## Unreleased — sessions and Git DevLogs

- Share immutable source snapshots and original fact-pack identity across all five
  formats; disclose campaign-context overrides and require renewed review (#46/#66).
- Refresh current X source maps/omissions after rewrites and label previous
  warnings as historical without changing original generation records (#47).
- Handle guidance-only Devlogs with an explicit empty highlight outline (#65).
- Distinguish release variants and clear input media briefs when loading facts (#67/#68).
- Add explicit versioned local session/profile Download/Open. Restore exact edits,
  X order/media, source selection and original failed/accepted attempts atomically;
  invalid imports preserve current work (#11).
- Add local Git range inspection, bounded selected-diff preview and one explicit
  Gemma request for fact candidates, followed by human selection and the existing
  Devlog editor. Retain commit/file provenance and committed-only scope (#8).
- Add optional local receipts for actual manual publications. Only an explicit
  receipt advances the saved repository baseline; no publication integration.
- Review corrections: save rejected-input attempts as original evidence, protect
  unfinished Git reviews when closing/replacing a tab, and allow bounded draft
  requests to carry the full supported provenance without a transport rejection.


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
