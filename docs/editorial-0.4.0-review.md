# PR #92 review against the 0.4.0 specification

Status update, 25 October 2026: the reviewed implementation was merged as `b8a5985`;
main CI passed on attempt 1. The review below records the pre-merge stage.
Current integration, draft and publication status: [main closeout](editorial-0.4.0-main-2026-10-25.md).

Reviewed head: `4ab33568a9aa500ce9682e3bce59ca51b165a0d5`; specification/base on
`main`: `9704298`. Review covers the shared document, inference/recovery, Quillgrain
contracts, block/media rendering, DEV delivery, X dependencies, UI persistence and
package/CI integration. Fixes stay on the draft PR branch; no merge or release.

## Findings and corrections

| Priority | Concrete trigger and former failure | Correction |
| --- | --- | --- |
| P1 | A retried first section/card succeeds, then the next fails. Another retry looked up the original failed child and requested the first again. Repeating a rejected article batch also rewrote it as a pending candidate. | Persist child selections and the batch outcome under the operation ID before inference. Reuse successful retries; preserve rejected/accepted outcomes. Freeze unfinished batches to their revision and runtime. |
| P1 | Rejecting a child section/card did not stop the combined batch from accepting it. A crash after applying the document but before updating attempt markers left acceptance/rejection ambiguous. | Validate child decisions under the same lock as acceptance; record accepted candidate IDs with the document/manifest commit. Recovery and UI derive acceptance from that durable record and never reapply over a later edit. |
| P1 | Another editor advances the reviewed article after the UI loaded it. DEV delivery ignored the displayed revision and sent the newer document. | CLI/API support expected revision; UI sends it, and delivery rejects a mismatch under the workspace lock before any remote access. The UI exposes title, target ID, revision and outgoing payload hash without network/key access. |
| P1 | Removing a cover omitted `main_image`, leaving the old cover on DEV. Adding a cover remotely to a previously coverless draft could also evade comparison. | Send an explicit null for removal; compare present `main_image`/`cover_image` fields even when no cover is desired. Unknown cover state blocks reconciliation. Historical receipts may require an explicit inspected remote hash after this stronger comparison. |
| P1 | Paragraph HTML/Liquid was escaped in local preview but exported verbatim to DEV. It could become a remote embed absent from the local view. | Serialize the preview's bounded inline grammar to safe Markdown, escape unsupported text/heading markup, and reject unsafe media-URL delimiters. Exact source code remains unchanged; Liquid in exact code blocks DEV delivery with a named error. |
| P1 | Unsaved outline reordering/addition/removal lived only in the JavaScript closure. Reload or another save could discard the arrangement even though text buffers survived. | Buffer the complete pending section arrangement, restore it with field edits and keep it pending until explicit plan save. Preserve restored field values across subsequent moves. |
| P2 | Expired evidence with a verified URL raised from X export, blocking the whole article preview; stale ready TXT files could survive reuse of an export folder. | X returns a separate blocked state. Article preview/export remains available, no ready X files are written, and export identity includes X readiness and render policy so old bundles remain intact. Acceptance rechecks evidence freshness too. |
| P2 | Public media URLs made the actual DEV body exceed 32000 characters, while validation counted shorter local paths. | Check both local and public serialized body lengths before committing the mutation. |
| P2 | A locked section's purpose/conditions could change through the outline. X prompts also received facts omitted from the article. | Protect the whole locked section plan, while allowing reorder; restrict announcement fact context to sources actually used by the accepted article. |
| P2 | The UI reused an accepted X operation ID, so asking for another generation returned the old proposal. The X diff's accepted side showed article sections. | Allocate a fresh operation after a terminal proposal; retain the ID for unfinished retries. Show accepted X cards as the comparison. Unsaved article edits must be saved/discarded before requesting inference. |

Public-link identity is also checked under the workspace lock after network verification,
so a concurrently created delivery receipt cannot be bypassed. Literal Markdown
delimiters remain visible instead of being mistaken for empty formatting. Desktop
anchor targets also clear the sticky navigation so section headings remain visible.

The cover correction follows Forem's permitted article attributes and its model's
allow-blank cover validation: [controller](https://github.com/forem/forem/blob/main/app/controllers/concerns/api/articles_controller.rb),
[model](https://github.com/forem/forem/blob/main/app/models/article.rb). This review uses
mocked remote responses to test removal/conflicts; it does not claim a new live API run.

## Verification

Nine initial regression cases failed on the reviewed head before fixes. The expanded
regressions cover repeated retries, rejected outcomes, runtime/revision conflicts,
dry-run purity, DEV revision/cover checks, exact code, safe Markdown/public body limits,
omitted source scope, tag expiry, export preservation and literal formatting delimiters.
Chromium cases cover plan-buffer restoration, pending-edit guards, displayed delivery
revision and a fresh X generation after acceptance, under the existing CSP.

The final full local regression run passed **466 tests with zero skips in 215.44s**,
including installed Quillgrain and actual Chromium. The 15 existing dependency
deprecation warnings remain; no new warning category was introduced.
Full local regression results are recorded in ignored `artifacts/editorial-review-suite.xml`.
The exact pushed head and first-attempt CI outcomes are attached to [draft PR #92](https://github.com/drevendev/PatchPitch/pull/92).
CI includes the base suite, pinned Quillgrain checks with zero-skip enforcement, wheel/sdist
builds, source-archive test collection and the installed headless CLI without UI packages.

No new model inference, live DEV writes, publication, tag or release is part of this review.
The prior two live materials remain engineering evidence. Owner assessment of narrative,
personal voice and measured author-time savings remains the release acceptance gate
described in the [original verification](editorial-0.4.0-verification.md).

Practical user experiments are documented [here](editorial-experiments.md).
