# Backlog

Updated 25 October 2026 after [PR #92 main integration](editorial-0.4.0-main-2026-10-25.md). **0.3.0 is released; the 0.4.0 editorial pipeline is merged and unreleased.** The open items below are follow-up work, not open gates for the documented 0.3.0 12B/600-second configuration. No work schedule is assigned.

X announcements remain on hold at the owner's request. The earlier 0.3.0 DEV/X article cycle is closed; Telegram was intentionally skipped. On 25 October the owner separately authorized polishing both engineering drafts and publishing one: the Quillgrain article is now public; the PatchPitch article remains a draft. No release or X publication accompanied this action. PyPI distribution has not been requested and is not an unfinished step of the GitHub release.

## 0.4.0 development — editorial article pipeline

Status: [specification](0.4.0-spec.md) committed to `main` in `9704298`; [PR #92](https://github.com/drevendev/PatchPitch/pull/92) merged into `main` on 25 October in `b8a5985337eb8a06995ccbf7f1718c09db3be0ec`. The shared CLI/studio pipeline now provides editable plans, scoped Quillgrain proposals, immutable revisions, section/block edits and locks, real-media preview/export, DEV draft synchronization and three linked X announcements. Details and live evidence: [verification report](editorial-0.4.0-verification.md); commands: [editorial guide](editorial.md).

Additional [PR #92 review](editorial-0.4.0-review.md) fixes repeated-retry/rejected-batch handling, DEV revision and cover synchronization, safe Markdown export, unsaved plan arrangement, independent X evidence blockers and public-body limits. [Main CI](https://github.com/drevendev/PatchPitch/actions/runs/40169936148) passed on **attempt 1**: **443 passed, 4 expected optional-engine skips** in the base job; **25 passed, zero skips** in the pinned Quillgrain job; wheel/sdist builds, **444 tests collected** from the source archive, clean installed CLI and editorial smoke checks passed. Suggested [product experiments](editorial-experiments.md) are available without public posting.

Automated regressions cover recovery, stale edits/exports, exact code/media preservation, DEV conflicts/disclosure/cover and X length/evidence/URL binding. Two real-model materials (PatchPitch and Quillgrain) initially reached private DEV drafts. After separate owner authorization, both were edited through PatchPitch and reviewed in DEV; [Quillgrain](https://dev.to/drevendev/i-verify-the-voice-context-before-i-ask-a-model-to-write-3gok) was published, while PatchPitch **4911995** remains a draft. Deletion was cancelled. All **105** inventoried original workspace files, including failed model attempts, are unchanged; edited copies and publication evidence are retained locally. This publication does not establish general voice quality or editing-time savings.

Before promoting a release candidate:

- Evaluate the pipeline's voice, narrative, accuracy and useful examples on further owner-selected material. The merged technical review and authorization for one article do not establish general editorial quality.
- Measure active author editing time against a comparable baseline before claiming time saved. Request counts and inference timings alone do not establish this.
- Keep model-output rejection visible: a supplementary imported-public-article experiment rejected narrow-topic/invalid-JSON X responses; no checks were relaxed. Operator-selected evidence, source context and manual editing remain part of the workflow.
- Recheck fresh catalog evidence when preparing real announcements. Version promotion, release and future publications still require separate owner authorization.

Existing X URL-counting and CSP test corrections below are carried forward, not reimplemented. DEV inline video with sound/controls remains the separate deferred item below; local video preview does not close it. Package version remains 0.3.0; no 0.4.0 release/tag or new hosting service was created. The separately authorized Quillgrain publication is recorded in the [main integration report](editorial-0.4.0-main-2026-10-25.md).

## DEV video with sound and controls

Status: deferred by the owner on 23 October 2026; outside the completed article publication cycle. No scheduled work or new hosting account is implied.

Investigate a supported way to play the demo **inside a DEV article**, with audible sound and visible play/pause, seek and volume controls. The current accepted fallback is a DEV CTA opening the GitHub Pages player.

Observed obstacle: DEV's Forem processing treats raw HTML video as GIF-like media. Its initializer forces muted looping playback and removes controls, including when `controls="controls"` is explicitly supplied. A plain MP4 link, external CTA or muted inline loop does not satisfy this backlog item.

Acceptance criteria:

- Use a supported DEV embed or native video feature; investigate supported video hosts, including YouTube when the owner is ready to set it up.
- Verify the saved DEV rendering in a browser: video plays inside the article, sound can be enabled, and play/pause, seeking and volume work.
- Check subtitles and responsive layout; retain the GitHub-hosted source and fallback player.
- Test in a draft first. Updating a published article or creating a hosting account remains a separate explicit action.

Context: [publication closeout](publication-closeout-2026-10-23.md).

## Small-model output acceptance

Status: open investigation; no general 4B support claim. The [Linux comparison](linux-live-2026-10-24.md#gemma-3-4b-completed-acceptance-failed) with `gemma3:4b` attempted all four targets and failed acceptance. The documented `gemma4:12b` configuration passed.

Investigate the observed failures: an X plan too narrow to support six catalog tags, Telegram language/source-ID leakage, and incomplete selected-fact coverage in DEV/GitHub output. Retain original failed responses as comparison evidence.

Acceptance criteria:

- Reproduce the failed campaign and determine whether prompt/model/runtime changes can improve its output.
- Preserve six evidence-backed X tags, source coverage, language and publication validation; do not relax checks to turn failures into passes.
- Before claiming another supported model, complete a real installed-package Linux run of all four targets, validation, session export and unchanged repeat/resume; record the model digest, runtime, timeout and raw evidence.
- Review the resulting text for meaning, language and unsupported claims in addition to automated checks.

## X catalog refresh and effectiveness evidence

Status: ongoing maintenance. The bundled [catalog](../examples/headless/x-catalog-2026-10-22.json) and [observation ledger](../examples/headless/x-observations-2026-10-22.json) are dated 22 October 2026; the catalog has a 30-day evidence window. Matching currently establishes topical relevance, not measured reach.

Acceptance criteria:

- Collect fresh real observations before relying on the catalog beyond its evidence window; retain timestamps, source references and topical reasons for each tag.
- Review the catalog/ledger together and verify six supported tags for the intended campaign. Keep stale/insufficient-evidence rejection and length reservation.
- Record actual outcome data before making effectiveness claims; do not substitute invented popularity scores. Any future public test posts require the owner's publication authorization.

No recurring collection or posting automation is enabled. See the [catalog guide](x-catalog.md).

## Completed after 0.3.0 — awaiting a future release

### CSP-safe delayed-regeneration browser test

Status: completed in `main` by [c2e337f](https://github.com/drevendev/PatchPitch/commit/c2e337fbce86aa0576720a54d32dece1f58346ae). The test and changelog changes are unreleased; no application CSP or release metadata was changed.

- Replaced both string-expression `wait_for_function` calls with retrying locator assertions for the Generate button. This removes the polling path that raised a CSP `EvalError` during failed regeneration.
- Retained successful and failed regeneration coverage: controls lock while a request is pending, then unlock; a failed request preserves the previous edit. The test also asserts that the served policy includes `script-src 'self'` without `unsafe-eval`; CSP is not bypassed.
- Ten consecutive local runs passed both cases (20 checks). The full local suite passed on its first attempt: **382 passed, zero skips** with Quillgrain installed.
- [CI for c2e337f](https://github.com/drevendev/PatchPitch/actions/runs/40106544985) passed on **attempt 1**, without a rerun: **363 passed, 3 expected optional-engine skips** in the base suite; **21 passed, zero skips** in the pinned Quillgrain job. Wheel/source builds, source test collection, clean-wheel installation and installed headless CLI verification also passed.

### X URL counting and generation budget (#91)

Status: completed in `main` by [9b21c80](https://github.com/drevendev/PatchPitch/commit/9b21c80e65b874b13a7d99af3bb4c9ed7efa238a); [#91](https://github.com/drevendev/PatchPitch/issues/91) is closed. This correction is unreleased; the published 0.3.0 tag and packages are unchanged.

- CLI and studio count each recognized URL as 23 characters, including long DEV links, query strings and UTM parameters. The same rule applies to final validation and generation space reserved for the CTA and six selected hashtags, including `#DEVCommunity` when requested.
- `x-estimate-v2` preserves historical responses, measurements and run snapshots. Current exports and editor validation use the corrected estimate.
- Expected-count fixtures cover URL boundaries, punctuation, multiple URLs and Python/JavaScript parity. CLI/UI checks accept a fitting 280-character post and reject 281; six-tag generation budgets are covered.
- [CI for the fix](https://github.com/drevendev/PatchPitch/actions/runs/40103922223) passed: 363 base tests with 3 expected optional-engine skips, 21 Quillgrain checks with no skips, and wheel/source builds with clean-install CLI verification.

The three prepared DEV article announcements now estimate at **176 / 185 / 178**, rather than 248 / 257 / 250. A shorter visible URL is not needed to recover X's character budget. Short.io and click-tracking integration remain deferred; no shortener account or service was added.

The extractor remains a bounded estimate: full twitter-text TLD/IDN and emoji conformance is not claimed. Unsupported or malformed URL candidates retain ordinary weight, and manual X preview remains required. Scope and historical-data handling: [X length guide](x-length.md).

## Closed with 0.3.0

- DEV uncertain-write recovery and omitted AI-disclosure regression coverage.
- Quillgrain pinned CI with zero skipped integration cases.
- Main synchronization preserving the newer README.
- Real Linux four-target acceptance on the documented 12B configuration.
- Candidate/final metadata and reviewed facts, final tests/package checks, annotated tag and GitHub Release.

Evidence and exact release identity: [0.3.0 closeout](release-closeout-0.3.0-2026-10-24.md).
