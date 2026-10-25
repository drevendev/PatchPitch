# Editorial pipeline: main integration and DEV follow-up

25 October 2026. The 0.4.0 implementation is merged and unreleased. Package version
remains **0.3.0**. No release, tag or X publication was created by this follow-up.

## Merge and first-attempt CI

[PR #92](https://github.com/drevendev/PatchPitch/pull/92) was marked ready and merged
at **2026-10-25 06:40:35 UTC**. The reviewed head was
`1b3cb86d192826b221f3618ca7ae312d7cdf4bcd`; the `main` merge commit is
`b8a5985337eb8a06995ccbf7f1718c09db3be0ec`. Their tracked file trees match.

[Main CI run 40169936148](https://github.com/drevendev/PatchPitch/actions/runs/40169936148)
completed successfully on **attempt 1**, without a rerun:

| Job | Result |
| --- | --- |
| Base tests | **443 passed, 4 expected optional-engine skips**, 15 existing warnings |
| Pinned Quillgrain | **25 passed, zero skips**; skipped-case rejection guard passed |
| Package | 0.3.0 wheel and sdist built; **444 tests collected** from the source archive; clean installed CLI without UI packages and editorial smoke checks passed |

The final local regression before merge passed **466 tests, zero skips**, with
Quillgrain installed. The different job counts reflect their environments and
selected tests; source-archive collection is not an additional full test execution.
The [review](editorial-0.4.0-review.md) and
[implementation report](editorial-0.4.0-verification.md) preserve earlier evidence.
The remaining release gates are tracked in the [backlog](backlog.md).

## Existing DEV drafts: edit instead of delete

The owner cancelled deletion and authorized polishing both existing drafts and
publishing one. Work used full local workspace copies, preserving document IDs,
sources, voice snapshots, attempts, revisions, receipts and media. Original
workspaces remain untouched: all **105** files in the pre-action SHA-256 inventory
still match. No DEV article was deleted and no additional article was created.

| Existing article | Final state |
| --- | --- |
| PatchPitch **4911995**, formerly “One local job, four drafts, and a failed 4B run” | Edited as **“I review four drafts from one local job”**; remains unpublished. Historical screenshot, GIF and external video CTA retain explicit 0.3.0 captions. |
| Quillgrain **4912136**, “I verify the voice context before I ask a model to write” | Edited and [published on DEV](https://dev.to/drevendev/i-verify-the-voice-context-before-i-ask-a-model-to-write-3gok) at **2026-10-25 07:04:38 UTC**, under the owner's separate authorization. |

Both edited materials passed PatchPitch article review and updated the existing
DEV IDs through draft-only delivery. Remote content was compared with the saved
pre-action copies before writing; historical cover normalization on the Quillgrain
receipt was resolved using the inspected remote hash. Both saved previews were
reviewed in a browser. Quillgrain publication was a separate, owner-authorized DEV
operation; PatchPitch's adapter remains draft-only. Public readback confirmed the
reviewed title, body, description, tags and cover state; the PatchPitch draft was
confirmed unpublished afterward. Existing AI disclosure was retained.

The Quillgrain example was re-executed locally with **0.1.0rc3** and the public
`examples/editorial/voice` pack: compile and verify succeeded; an English bundle
verified against a Russian request failed with `VOICE_LANGUAGE_MISMATCH`. These
checks made **zero inference requests**. The article identifies the tested version
and distinguishes explicit editorial preferences from a learned personal voice.

## Local evidence and remaining work

Private evidence remains ignored under `artifacts/`:

- `pr92-main-merge-verification.json`: merge and CI snapshot before the later publication authorization.
- `dev-draft-cleanup-2026-10-25/`: original remote copies, file hash inventory and deletion-cancellation decision.
- `dev-editorial-polish-2026-10-25/`: edited workspace copies, exports, compile/verify proof, remote receipts, reviewed screenshots and publication readback.
- Original `editorial-example-smoke/` and `editorial-quillgrain-live/`: unchanged engineering runs; their DEV receipts describe historical draft states, not the current publication state. Use the edited copies and publication record for current state.

Further owner quality experiments and a comparable active-editing-time baseline
remain open. Fresh X catalog evidence is required for future announcements. Small
model acceptance, DEV inline video with sound/controls and optional link analytics
remain deferred or under investigation as described in the backlog. This single
publication does not establish general writing-quality or time-saving claims.
