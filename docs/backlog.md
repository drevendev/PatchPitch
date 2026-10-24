# Backlog

Updated 24 October 2026 after [0.3.0 release closeout](release-closeout-0.3.0-2026-10-24.md). **0.3.0 is released.** The items below are follow-up work, not open gates for the documented 12B/600-second configuration. No next-release version or work schedule is assigned.

New announcements remain on hold at the owner's request. The earlier DEV/X article cycle is closed; Telegram was intentionally skipped. PyPI distribution has not been requested and is not an unfinished step of this GitHub release.

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

## Closed with 0.3.0

- DEV uncertain-write recovery and omitted AI-disclosure regression coverage.
- Quillgrain pinned CI with zero skipped integration cases.
- Main synchronization preserving the newer README.
- Real Linux four-target acceptance on the documented 12B configuration.
- Candidate/final metadata and reviewed facts, final tests/package checks, annotated tag and GitHub Release.

Evidence and exact release identity: [0.3.0 closeout](release-closeout-0.3.0-2026-10-24.md).
