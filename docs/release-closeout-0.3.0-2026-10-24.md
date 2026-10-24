# PatchPitch 0.3.0 release closeout — 24 October 2026

Status: **released**. [GitHub Release v0.3.0](https://github.com/drevendev/PatchPitch/releases/tag/v0.3.0) was published at **2026-10-24T12:33:01Z** (15:33:01 Asia/Nicosia), with the owner's authorization. It is a stable release, not a draft or prerelease.

## Released source and files

- Final source commit on main: `e5a39f6aba15caba936473787d0142b8cbe25b7c` (`release: finalize PatchPitch 0.3.0`).
- Annotated tag: `v0.3.0`, pointing to that commit. Tag object: `ef0db132257dd338166c393ea707433b199af76f`.
- Reviewed source range: [`44ca597...v0.3.0`](https://github.com/drevendev/PatchPitch/compare/44ca597...v0.3.0).
- [Release notes](releases/0.3.0.md) and [headless operating guide](headless.md) describe installation, supported configuration and limitations.

The release contains the exact wheel and source archive built and checked by final-commit CI. Server-reported SHA-256 digests matched the downloaded CI files before closeout.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `patchpitch-0.3.0-py3-none-any.whl` | 480773 | `455ef852803f5cb1356aab31d63e5e488fdf697d5e8fab92f76ef15a50855def` |
| `patchpitch-0.3.0.tar.gz` | 637657 | `48c9e6c01b4369b1ebe1d7c29db8f466e469eea27fb53e819f2025935e50d53e` |
| `SHA256SUMS` | 190 | `788cc9809642b7a1c591aa6a8f13dd6b3584968a41a4852c845bb796fef000bf` |
| `SOURCE_COMMIT` | 41 | `138d41450bb77214e82ccfa4f1d147c71dbeeb13e13631ee876ac0034830f5a4` |

`SHA256SUMS` uses plain archive filenames. `SOURCE_COMMIT` contains the full source SHA above. No package-index/PyPI upload was performed.

## Verification completed

Both [final main CI](https://github.com/drevendev/PatchPitch/actions/runs/40094090992) and [tag CI](https://github.com/drevendev/PatchPitch/actions/runs/40094315604) passed all three jobs: `tests`, `quillgrain`, `package`.

- Final local Windows suite: **334 passed, zero skipped**, 15 dependency deprecation warnings, 200.71 seconds.
- Main Linux base job: **315 passed, three expected skips**, 15 warnings. The skipped optional-engine checks are covered by the dedicated integration job; a skipped module represents multiple cases.
- Pinned Quillgrain integration: **21 passed, zero skipped**, engine `0.1.0rc3` at revision `8af17f979c0ad20163bec5fd247279a7a6f5addf`. The job rejects skipped integration checks. Across base/integration jobs there are 334 distinct passing cases; two cases run in both jobs.
- Package job: wheel/source build, source-archive test collection, clean installed-wheel CLI/schema/four-target-plan smoke outside checkout without UI dependencies, and archive checksum/source records.
- Test discovery is explicitly scoped to `tests/`; extracted source archives under ignored evidence directories no longer shadow the real suite.

The [Linux real-model acceptance](linux-live-2026-10-24.md) passed all four targets, validation, session export and unchanged repeat/resume on Ubuntu 24.04 with Ollama 0.40.10, `gemma4:12b` and `PATCHPITCH_TIMEOUT=600`. Five real requests took 1599.653 seconds; repeat/resume made no further requests. [Live run](https://github.com/drevendev/PatchPitch/actions/runs/40079916968).

That live run used the development version before final promotion. Its original responses and fingerprints remain unchanged; it is not a new inference run of the final-version package. Final promotion changed metadata, reviewed release facts, documentation and test discovery, not inference/validation behavior. Quillgrain compilation/scope/browser acceptance is established separately by integration CI; the four-target Linux sample did not use a live Quillgrain voice.

## Closed release work

- Unattended CLI campaigns for Telegram, X, DEV and GitHub, persistent attempts, explicit resume, validation and session export.
- Exactly six catalog-backed X tags with planning, reserved length and edited-output validation.
- Optional Quillgrain integration and mandatory pinned integration CI.
- DEV draft delivery/recovery with exact saved outgoing payload, omitted-disclosure handling and regression coverage, without duplicate blind creation or weakened ownership/publication checks.
- Main integration preserving the newer offline-first README; Linux acceptance, candidate review, final version/facts, package checks, tag and GitHub Release.

No blocker remains for the documented 12B/600-second release configuration. The independent Gemma 3 4B run failed output acceptance; it remains a known limitation, not evidence of equivalent support. DEV took 497.921 seconds on the tested CPU, so the normal 420-second timeout was not sufficient for that run. Tag matching is lexical and does not measure reach. Output still needs editorial review. These limits remain in the release notes and [backlog](backlog.md).

The 15 local dependency warnings were non-blocking deprecations; they were not test failures or additional skipped release gates.

## Publication boundary and remaining work

The [23 October article cycle](publication-closeout-2026-10-23.md) remains separately closed: DEV article published, X posting confirmed by the owner, Telegram intentionally skipped. The accepted video fallback opens the GitHub Pages player with sound and controls. Native inline DEV playback remains deferred.

**No new X, Telegram, DEV or other announcement was published for this software release. New announcements remain on hold at the owner's request.** Remaining work and acceptance criteria are in the [project backlog](backlog.md); no new schedule or hosting account was created.

Local verification receipts and downloaded release files are retained under ignored `artifacts/release-0.3.0/publication-receipt.json` and `artifacts/release-030-ci/`. They are local evidence, not tracked assets; the release URLs, source identity and checksums above provide the durable public record.
