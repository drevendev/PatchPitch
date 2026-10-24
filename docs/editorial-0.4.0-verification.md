# Editorial pipeline implementation and verification

24 October 2026. Branch: `codex/0.4.0-editorial-pipeline`; base specification committed
and pushed to `main` as `9704298`. This is development work for a draft PR. Package
version remains **0.3.0**; no version promotion, release, tag or public announcement.

## Delivered behavior

The [specification](0.4.0-spec.md) is implemented through a separate versioned workspace,
shared by `patchpitch editorial` and `/editorial`. Original campaign runs and sessions
retain their contracts. Source import reads existing runs without rewriting them.

| Stage | Implementation and evidence |
| --- | --- |
| Plan and document | Stable IDs/tombstones, source omissions, metadata, typed blocks, compare-and-swap, atomic immutable revisions and explicit reviews |
| Writing | Quillgrain snapshots, outline/section proposals and diffs, accept/reject, locked sections, saved raw responses, bounded requests and explicit recovery/retry |
| Editing | Paragraph/list/code/media blocks, ordering, per-section edits, historical restore and private workspace backup; neighboring unsaved fields survive a save/reload; switching folders clears previous preview/X cards |
| Media | Original PNG/JPEG/WebP/GIF/MP4/WebVTT imports, signatures/hashes/limits, alt/cover/captions, portable local playback, desktop/mobile preview under strict CSP |
| DEV | Draft-only POST/PUT, public media mappings, cover DTO comparison, ownership/publication guards, remote-edit conflicts, uncertain-response reconciliation and explicit visual review |
| X | Three checkpointed standalone candidates, one-card rewrites/manual edits, six dated evidence-backed tags including publication-context `#DEVCommunity`, stale dependencies, typed URL slot and offline final export |
| Packaging | CLI has no UI dependency; wheel/sdist checks exercise editorial schema/init/preview; pinned Quillgrain CI includes the new integration cases |

Code and media blocks do not depend on the model repeating their bytes: inference
returns prose paragraphs, and the application places exact selected references.
Historical exports remain separate when content, the X series or its URL changes.

## Real local model acceptance

Environment: Windows, Python 3.12, Ollama **0.40.6**, `gemma4:12b`, timeout **600s**.
Model digest observed on this machine:
`6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b`.
Attempts retain their exact payload/options, source runtime fingerprint and raw reply.
These are new local observations; the older Linux 0.3.0 timings are article source
facts, not a 0.4.0 benchmark or evidence of a new Linux editorial run.

Both materials use the checked-in **designed demonstration profile**, compiled by
Quillgrain 0.1.0rc3 for the appropriate longform/X scopes. This is not a learned
personal profile. Snapshot hash:
`8e16fb0ac9a6d159921540f8d8bc25380cc3e18b6fd4909ea6d518768dfb067d`.

| Material | Requests, including retained failures | Sum of measured inference calls | Outcome |
| --- | ---: | ---: | --- |
| PatchPitch from reviewed 0.3.0 facts | 14 | 250.333s | Accepted four-section article, single-section rewrite, manual edits, locked neighboring section, real media and three X candidates; private DEV draft **4911995** |
| Quillgrain from inspected engine/API facts and an executed compilation example | 7 | 70.881s | Accepted three-section article and exact Python example; three X candidates; private DEV draft **4912136** |

These sums exclude operator edits, preview/export and network delivery; they are not
time-to-publication or author-time measurements. The second material needed an opening
edit and two X angle edits, rather than a complete external rewrite. The PatchPitch
material needed factual framing/command-caption edits; the three unselected sections
were compared before/after its targeted model rewrite and remained identical.

Early PatchPitch attempts exposed missing paragraph citations and model-rewritten code;
the prose-only schema and application-owned code placement fixed that contract. Early X
attempts had insufficient topic evidence; the final three-request series passed with
the full observed catalog. The successful Quillgrain series also used that catalog.
Operator edits clarified claims and diversified angles; originals remain available.

The PatchPitch draft uses existing owner-hosted screenshots, GIF, cover, a 42-second
MP4 with audio, poster and WebVTT. Captions explicitly identify this as historical
0.3.0 media, not a new recording of the 0.4.0 editor. No new hosting service or upload
account was created. Local browser checks cover controls, unmuted playback, seeking,
subtitles and mobile width using a real two-second audio/video fixture as well.

## Live delivery, recovery and URL checks

- Both DEV materials were confirmed **unpublished** through the owned-article API and
  authenticated browser preview. No secret preview URLs are recorded here.
- The PatchPitch draft retained ID **4911995** on unchanged repeat and subsequent
  updates. A controlled real remote edit was detected; explicit reviewed-hash
  resolution updated that same draft.
- A real PUT followed by a deliberately simulated lost client response exercised
  uncertain-write recovery. A blind repeat was blocked, reconciliation used the saved
  original payload, and a later local edit survived. This was a response-loss simulation,
  not an observed DEV service outage. The live DTO omitted AI disclosure and used the
  cover alias; both were handled without inventing remote field values.
- Actual saved DEV rendering showed the cover, headings, screenshot and GIF. Video
  remains a poster/CTA to the accepted external player, not an inline DEV video claim.
  Explicit visual-review receipts were recorded separately from successful HTTP writes.
- Final-URL verification succeeded read-only against the already public article
  **4910718**, imported into a separate reference workspace. No model request was
  triggered by binding. Binding that older article to a different newly delivered
  draft correctly failed with `ARTICLE_ID_MISMATCH`.
- Supplementary X generation for that imported article retained rejected narrow-topic
  and malformed-JSON replies. It did not produce a third accepted series. Two new
  materials have accepted series awaiting their own future public URLs; substituting
  an unrelated URL to make an end-to-end demo look green would violate the ID guard.
  Deterministic three-TXT replacement, URL weight and zero-inference binding are also
  covered by automated tests. No X post was sent.

Private local evidence is kept under ignored `artifacts/`: the two workspaces,
`editorial-live-evidence.json`, `editorial-live-dev-verification.json`, browser screenshots
and the test XML. Raw voices, receipts, source paths and responses are excluded from
publication exports and from this public report.

## Verification and remaining review

The final local suite passed **436 tests, zero skips, in 168.21s**, with installed
Quillgrain and actual Chromium; 15 existing dependency deprecation warnings remain.
Results are recorded in `artifacts/editorial-final-suite.xml`; the four editorial browser cases also passed a targeted final repeat, including full candidate source-map visibility before acceptance. CI runs base
tests without the optional engine, a separate pinned Quillgrain job with skipped-case
rejection, and wheel/source builds plus clean installed CLI smoke checks. Inspect the
draft PR checks for the exact final commit; the first implementation commit also
[passed all three jobs](https://github.com/drevendev/PatchPitch/actions/runs/40122471268).

The technical workflow is implemented; the owner's editorial acceptance of voice,
story quality and usefulness is still a review gate. Active author editing time and a
comparable manual-workflow baseline were not measured, so no time-saving percentage
is claimed. Model rejection and explicit operator review remain visible parts of the
workflow. These limits do not authorize a release or public posting.

Deferred items remain in the [backlog](backlog.md): inline DEV video with audio/controls,
small-model acceptance, observed catalog refresh and actual effectiveness measurements.
