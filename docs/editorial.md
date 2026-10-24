# Editorial article workspace (0.4.0 development)

This is an unreleased workflow on the implementation branch. Existing 0.3.0
campaign/session commands keep their contracts. The [specification](0.4.0-spec.md)
defines the product acceptance gates; a draft PR is not a release.
Try the [guided experiments](editorial-experiments.md); the subsequent
[PR review](editorial-0.4.0-review.md) records additional regression fixes.

## Start locally

Install PatchPitch and, for author profiles, the trusted Quillgrain 0.1.0rc3 engine
as described in [voice setup](quillgrain-voice.md). Prepare Ollama only for writing;
opening, editing, preview and export do not need a model. Paths in TOML are relative
to that file. Use a new empty folder for each initialized workspace.

```text
patchpitch editorial init --config examples/editorial/article.toml --out artifacts/my-article --json
patchpitch editorial status --work artifacts/my-article --json
patchpitch editorial outline --work artifacts/my-article --operation-id first-outline --dry-run --json
patchpitch editorial outline --work artifacts/my-article --operation-id first-outline --json
```

The example compiles a **designed public demonstration profile**, not a learned
personal voice, and uses the reviewed historical 0.3.0 fact pack. For a preset-only
example use `examples/editorial/article-preset.toml`. No profile or model is installed
automatically. The dated tag catalog needs fresh observations after its evidence
window; its source ledger is [here](../examples/headless/x-observations-2026-10-22.json),
with a separate [DEV community observation](../examples/editorial/devcommunity-observation-2026-10-24.json).
Those small topical samples do not establish reach.

## Accept, edit and review

Outline/draft/rewrite operations save candidates under `attempts/`. Inspect them,
then accept against the displayed base revision:

```text
patchpitch editorial accept --work artifacts/my-article --candidate first-outline --expected-revision REVISION_FROM_SUMMARY --json
patchpitch editorial apply --work artifacts/my-article --patch review-plan.json --json
patchpitch editorial draft --work artifacts/my-article --operation-id first-draft --json
```

An explicit patch has this shape; copy the current revision from `status`:

```json
{
  "operation_id": "review-sources-and-plan",
  "expected_revision_id": "REVISION_FROM_STATUS",
  "operations": [{"type": "review_sources"}, {"type": "review_outline"}]
}
```

`draft` checkpoints each missing section and provides one combined candidate for
accepting the completed batch. A failed section preserves earlier candidates. Repeat
with the same operation ID to reuse completed responses; an unknown outcome never
silently starts another inference. A saved raw response can be recovered with:

```text
patchpitch editorial recover --work artifacts/my-article --candidate ATTEMPT_ID --json
patchpitch editorial revise --work artifacts/my-article --section S02 --instruction-file change.txt --operation-id revise-s02 --json
patchpitch editorial reject --work artifacts/my-article --candidate ATTEMPT_ID --json
patchpitch editorial draft --work artifacts/my-article --operation-id first-draft --retry-failed --json
```

Recovery of unfinished inference requires its original runtime/model configuration.
Read-only preview/export of accepted work remains available without the compiler.
Manual edits use `apply` with `section`, `outline`, `metadata`, `asset`, `voice`,
`lock_section`, `review_section`, `review_article`, `narrator` or `rollback` operations.
All mutation IDs are idempotent; stale expected revisions fail before replacing work.
Sections and blocks have stable IDs. Deleted IDs are reserved rather than reassigned.
The model writes paragraph slots only; the application inserts the approved exact code
and media references. A rewrite preserves existing code/list/media slots and bytes.
An accepted candidate is still a draft: review sources, outline, meaning, title,
description and conditions, then explicitly `review_article` for that content.

For arbitrary Markdown, use explicit import rather than editing a generated export:

```text
patchpitch editorial import-markdown --work artifacts/my-article --file edited.md --source-map section-sources.json --operation-id import-one --json
```

The source map is an author-declared mapping such as `{"S01":["C01"],"S02":["C02"]}`.
Imported `##` headings must match the accepted outline. Missing citations, unknown
media or unsourced code leave an unaccepted `needs_review` candidate. Front matter is
rejected, including publication flags. Exact source code uses snippet-reference blocks.
Import never inherits historical citations as a claim that the changed text is verified.

## Studio and recovery

Run the existing optional UI server and open `/editorial`, or use **Open the editorial
article workspace** from the home page. Choose the article folder. Create from a
reviewed facts JSON, optional longform/X bundles and dated catalog, or initialize
via CLI and open the same folder. Plan, sections, metadata and media use the same
operations as CLI. Proposed changes show accepted/proposed text before acceptance.

Accepted work is saved in the explicit local folder. Unsaved studio field edits are
buffered in browser local storage for the same workspace/revision and are labelled
when restored. Buffers are private and are not an accepted revision. A server error
leaves current editors intact. Keep the whole folder private: it contains sources,
voice profiles, model responses and remote draft receipts.

## Real media and preview

Import media with an explicit patch operation:

```json
{
  "type": "import_media", "id": "demo", "path": "C:/Media/demo.mp4",
  "provenance": "My recorded demo", "caption": "A real editor session"
}
```

Supported files: PNG/JPEG/WebP, GIF, MP4 and UTF-8 WebVTT. Import copies original
bytes into content-addressed local storage; no recording, download or transcoding
occurs. Files/signatures, sizes, dimensions and hashes are checked. Container metadata
may identify MP4 audio/duration; unknown metadata stays unknown. The browser still
must be able to decode the file. Limits: 30 files, 20 MiB per image/GIF/subtitle,
200 MiB per MP4, 500 MiB total, and 64 megapixels per image.

Use `asset` to set alt/caption, `poster_id`, `subtitle_id` and `public_url`; use a
section `media` block to place the asset. A cover is `metadata.cover_asset_id`.
The studio provides these controls. Alt is required for informative images.

```text
patchpitch editorial preview --work artifacts/my-article --out artifacts/my-preview --json
patchpitch editorial export --work artifacts/my-article --out artifacts/my-export --json
patchpitch editorial export --work artifacts/my-article --kind workspace --out PRIVATE_BACKUP_FOLDER --json
```

The first two write a static publication bundle with local and DEV-export previews,
Markdown, metadata and used assets. Serve the static bundle on loopback or follow
the studio's generated preview link. Video has controls and no forced mute/autoplay;
available WebVTT is attached. Inline Markdown is deliberately limited to escaped
text, emphasis, code and ordinary links; typed blocks render headings, lists and
exact code. Arbitrary HTML/Liquid is never executed.

DEV approximation shows public assets as links/placeholders to avoid automatic remote
loads; it is not Forem rendering. Inspect the actual saved DEV draft for final layout.
The existing accepted video fallback is a poster/CTA opening an external player.
Local MP4 playback does not close the separate DEV inline-video backlog item.

Publication exports contain no voice snapshots, raw responses, private provenance or
absolute source paths. The explicit **workspace** bundle is different: it contains
the complete private history for reopening. Exported Markdown is derived output;
if changed externally, reuse is blocked until an explicit import or a new export folder.
Earlier exports also remain intact when the article, accepted X series or bound URL
changes: use a new output folder. The studio automatically selects a separate folder
for that dependency state, preventing stale TXT files from appearing as current output.

## DEV draft and X

Give each used media file its already-hosted public HTTPS mapping. Unresolved media
blocks delivery; no hosting account/upload service is created. Configure the existing
`PATCHPITCH_DEV_API_KEY` only in the process environment. Then explicitly deliver:

```text
patchpitch editorial deliver --work artifacts/my-article --channel dev --mode draft --json
patchpitch editorial remote --work artifacts/my-article --json
```

`--preflight` explicitly checks public media over HTTPS. A single owned draft is created
or updated with `published=false`, cover and explicit AI disclosure. Remote content
changes produce a conflict instead of being overwritten. Inspect the remote/local
diff, then either import the remote Markdown or explicitly deliver with the inspected
`--remote-hash HASH`. A missing/unknown remote state blocks a blind update. An uncertain
write requires `--existing-id ID` reconciliation against the exact previously submitted
payload; later local edits remain intact. Already-published articles are never reverted.
HTTP success is delivery evidence, not visual acceptance; inspect the actual draft.

After viewing it, record that explicit review for the current revision:

```text
patchpitch editorial review-dev-preview --work artifacts/my-article --expected-revision REVISION --json
```

This rechecks local and remote hashes; a later edit invalidates the attestation.
Forem may expose a submitted `main_image` as `cover_image`; that DTO alias is compared
without changing the saved outgoing payload.

```text
patchpitch editorial x --work artifacts/my-article --operation-id x-first --json
patchpitch editorial accept --work artifacts/my-article --candidate x-first --expected-revision REVISION --json
patchpitch editorial x --work artifacts/my-article --post P02 --operation-id x-rewrite-two --json
patchpitch editorial edit-x --work artifacts/my-article --post P02 --text-file words.txt --json
patchpitch editorial edit-x --work artifacts/my-article --reaffirm --json
patchpitch editorial bind-url --work artifacts/my-article --url FINAL_DEV_URL --verify --json
```

Three distinct standalone announcements are candidates tied to article content.
The full series uses three checkpointed model requests; a one-post rewrite uses one.
`x --operation-id SAME_ID --retry-failed` explicitly retries failed children while
reusing successful ones. Unknown outcomes need inspection/recovery first. Original
model source IDs and application-selected product-context IDs are recorded separately.
Exactly six tags are reserved and checked; five describe evidenced product topics,
and required `#DEVCommunity` uses explicit **publication-context** evidence with the
same freshness/audience checks. It is not a fabricated product fact. A stale article
requires re-review and regeneration or explicit reaffirmation. One-post rewriting
preserves the other two posts. Manual variants are labelled editorial, not model output.

Before final binding, the managed URL slot reserves 23 X characters but is not
copy-ready text. Binding calls no model. `--verify` confirms public DEV identity;
private preview/query links are rejected. Final export rechecks full length and fresh
tag evidence, then writes three TXT files and a Markdown/JSON series. Nothing posts to X.
When this workspace has a DEV draft receipt, the public URL must resolve to that same
article ID. An unrelated already-published article cannot stand in for a new draft.

Expired tag evidence blocks only ready X output, not the article preview. The studio
shows its reason and preserves the old series. Rejected batches need a new operation
ID; repeat/retry of unfinished work retains the selected child attempts and runtime.
DEV delivery accepts `--expected-revision REVISION`; the studio always sends its
displayed revision. A cover removal is explicit in the outgoing payload.
