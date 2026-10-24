# 0.2.0 review candidate: Social Field Test

Moved from the README on 2026-10-23 so that the README can start with a first run.
The text is unchanged apart from one relative link. See also the [review record and release gates](0.2.0-review.md).

Current follow-up: the unreleased [#91 correction](x-length.md) replaces the URL
weighting described below with `x-estimate-v2`. The v1 observations in this
historical candidate record are preserved.

This candidate adds **X Single** and **X Thread** (3–7 posts, default five).
Load **Reviewed fact packs**, inspect their provenance, confirm the selected
facts and voice brief, then choose the X format and writing goal. Built-in inputs
cover PatchPitch's existing public workflow and the historical Idle Fantasy Shop
0.12 patch. Neither fixture establishes that a new version shipped today.
You can import a versioned fact-pack JSON using the same schema as
`patchpitch/fact_packs/patchpitch.json`; loading it never runs inference.

Each generated card has an editable plain-text post, source IDs, a length estimate,
Copy and an optional media note. Move cards up/down or explicitly regenerate one;
other cards and their edits are retained. The generated source snapshot stays
attached to its product/release, even after changing the input. Manual edits to
the raw input clear its pack provenance; review that new selection again.
Existing devlog/community/short formats continue to work.

X lengths use **x-estimate-v1**, a conservative estimate based on NFC, v3 character
weight ranges and a URL reserve. Emoji sequences can be overcounted and long URLs
keep their raw weight. This is **not twitter-text conformance or an X API validator**:
verify every final post in X. Overflow is reported without truncation or retries.
The generated exact CTA appears only on the final card; moving/editing cards
leaves the author's text intact. Single-card regeneration retains that card's
exact original CTA only if it is still present there. Media notes stay outside
per-post clipboard text and appear separately in the whole-thread Markdown.

Drafts for different products/releases/formats stay in this tab's memory.
A close/refresh warning is best effort. Use **Download session** to keep and
restore work, or export plain text/UTF-8 Markdown for publishing.
Nothing is posted to X and there are no platform credentials or cloud fallbacks.

The project author accepted the three edited pilot texts and the application.
The real X composer check was explicitly deferred; it has not passed.
See the [review record and release gates](0.2.0-review.md). Preparing the PR
and running its CI do not create a Release or deploy the staged Pages update.

## Live evidence

For explicit live evidence, with the app and model running:

```powershell
.\.venv\Scripts\python.exe scripts/social_pilot.py --live --case all
```

This performs one real request per case, checks clipboard/download, and retains
each attempt under ignored `artifacts/release-0.2.0/<head-sha>/`. Records distinguish
dirty source-tree hashes, configured and returned model identity, observed
health/tags digest, raw response, final text and failures. Missing identity is
unknown, not inferred. A health digest is not an inference-returned digest.
Rejected model output is retained as local error evidence. New pilot captures
start with owner acceptance and X preview marked `NOT_RUN`; later owner decisions
are recorded separately instead of rewriting the original capture.
Use `--interactive-review` to pause after each real response for explicit operator
edits before clipboard/download verification; this still does not imply owner approval.
