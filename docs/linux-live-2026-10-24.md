# Linux real-model acceptance — 24 October 2026

Current project status: **0.3.0 released**; see the [release closeout](release-closeout-0.3.0-2026-10-24.md). Final metadata/facts, package checks, tag and GitHub Release are complete. The experiment below retains its original development-version evidence. Its former release blockers and release holds describe that stage; remaining model/media/catalog follow-up is in the [backlog](backlog.md).

Experiment status: **Linux four-target runtime acceptance passed with Gemma 4 12B.** The independent 4B comparison failed output acceptance. No platform post, remote draft, software release or release tag was created by this experiment.

The owner authorized GitHub Actions because this Windows host has no WSL/Docker environment or running Ollama. Work is isolated on `codex/linux-live-030-20261024`; main remains at `f2ecdd2`. The tested application/package sources are unchanged from that development commit. The branch adds only the acceptance workflow and evidence harness.

## Method

Ubuntu 24.04 x86_64 hosted runner; Python 3.12.15. A new venv installs the package through pip. The installed CLI runs from a temporary directory outside checkout with stdin closed (`DEVNULL`). Probe confirms version `0.3.0.dev0` and no FastAPI/uvicorn/Playwright imports. The official Ollama 0.40.10 distribution runs on loopback with one inference slot. No publisher command or platform credential is used.

Inputs are the committed `examples/headless/all-four.toml`, reviewed facts/profile, dated X catalog and observation ledger. Five model requests are planned (X planning/writing plus three other formats); no automatic retries or repairs. Raw attempts and rejected responses remain separate from editorial observations. Completion also requires validation, session export and unchanged repeat/resume files.

## Gemma 3 4B: completed, acceptance failed

[Actions run 40081001495](https://github.com/drevendev/PatchPitch/actions/runs/40081001495), harness revision `b997066ee7655eb501f137422790927f4ad347ac`.

Model: `gemma3:4b`, digest `68ceab7e468a31c988b44d5a4984a0e21f58c4f7158c6ce29c1804babac38df7`, Q4_K_M, 3.9B parameters, downloaded size 3,350,272,403 bytes. Kernel: `6.17.0-1022-azure`. The Ollama log reports CPU compute, 15.6 GiB RAM (14.5 GiB initially available) and four logical CPUs; the model uses two inference threads. These are observations of one runner, not benchmarks.

Campaign elapsed: **183.374 s**, four actual model requests, exit **4**. All targets were attempted; processing continued after failures. X writing was not invoked because tag selection failed first.

| Target | Observation | Result |
| --- | --- | --- |
| X EN | Model planned a narrow local-Ollama topic citing C01; only four catalog tags matched. | `HASHTAGS_INSUFFICIENT_EVIDENCE`; no fabricated extra tags or exported post. |
| Telegram RU | Raw prose contains C01–C06. Editorial inspection also found English prose despite the Russian target and unsupported personal-experience wording. | `invalid_draft`; rejected. |
| DEV EN | Raw response covers only C01, leaving selected facts absent. | `invalid_draft`; rejected. |
| GitHub EN | Raw response covers C01 and code source C06, leaving the other selected facts absent. | `invalid_draft`; rejected. |

Telegram/DEV/GitHub request times: 72.676 s / 46.084 s / 40.112 s. No accepted original result exists; validation reports all four targets not ready. Session-export/reuse acceptance was not run because generation did not succeed. The validators blocked incomplete outputs; this is not a successful release acceptance run.

Local downloaded evidence: ignored `artifacts/linux-live-2026-10-24/gemma3-4b/`, with the original artifact directory, `report.json`, snapshots, model envelopes and errors; separate editorial notes are `artifacts/linux-live-2026-10-24/gemma3-4b-editorial-review.json`. The Actions artifact retains the public-input evidence for seven days; the local copy preserves it longer. No private voice pack is uploaded. All 20 evidence-manifest file hashes were verified after downloading.

## Gemma 4 12B

[Actions run 40079916968](https://github.com/drevendev/PatchPitch/actions/runs/40079916968), harness revision `e083d9b3a5179cd241206ae6b55061939ca645b4`. Completed successfully. Model `gemma4:12b`, digest `6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b` (matches the earlier Windows model digest), Q4_K_M, 11.9B parameters, downloaded size 8,021,618,941 bytes.

The campaign completed in **1599.653 seconds (26 min 40 s)**, exit **0**, with **five real Ollama chat requests**. The server log independently contains exactly five `/api/chat` POST entries. All four targets succeeded; validation and session export passed. Repeated `run` and explicit `resume` completed in 0.352 / 0.329 seconds, left all campaign files byte-identical, and made no additional chat requests. Session SHA-256: `58d09f4e642cbb9243abdaf11e77ad6ae6db26e1ab6fe8734545a1fd4c139ae5`.

| Target | Observed request time | Result |
| --- | --- | --- |
| X EN | Plan 124.834 s + write 179.148 s | Accepted, six tags, conservative estimate 272/280. |
| Telegram RU | 399.657 s | Accepted, Russian prose. |
| DEV EN | 497.921 s | Accepted; all selected facts and exact example command. |
| GitHub EN | 397.662 s | Accepted; all selected facts and exact example command. |

X tags: `#DevTools #LocalAI #LLM #Ollama #OpenSource #Automation`. Input, model responses and edits were not changed to obtain this pass. The 4B comparison used the same input hashes in a separate job; it remains recorded as a failure.

**Runtime requirement found:** this CPU run uses `PATCHPITCH_TIMEOUT=600`; the 497.921-second DEV request exceeds the application's default 420-second timeout. This is a tested configuration, not a promise for arbitrary CPU hardware. Keep the explicit timeout in Linux reproduction instructions.

All **50** downloaded evidence-manifest hashes were verified. Raw local evidence is under ignored `artifacts/linux-live-2026-10-24/gemma4-12b/`; independent editorial notes are `artifacts/linux-live-2026-10-24/gemma4-12b-editorial-review.json`. Agent reading found minor Telegram grammar issues and functional README-like longform prose. These are unpublished test drafts, not newly approved publication copy. The fixture's historical delivery-test caveats should be refreshed for final release facts.

## Release-gate assessment at the experiment stage

- **Linux live gate H01 is now closed for the documented 12B/600-second configuration.** Fresh installed-package execution, real inference, four accepted outputs, validation, export and unchanged reuse are established. This run does not include Quillgrain voice generation; Linux Quillgrain compilation/scope/browser coverage is supplied separately by its passing integration CI job.
- **Model/runtime support must stay explicit.** Gemma 3 4B failed this six-fact campaign and must not be advertised as equivalent. Preserve evidence-backed six-tag and source-coverage rejection. A claim of general 4B support requires separate improvements and a passing live run; it does not negate the verified 12B result.
- **Final candidate/source facts and release metadata remain pending.** Freeze the release commit/range, refresh the reviewed release fact pack and editorial copy, set the final version/notes, then perform final candidate smoke checks. The current version deliberately remains `0.3.0.dev0`; no final tag or release was authorized.
- Keep the explicit Linux timeout/model instructions. Ordinary 420-second defaults were not the configuration tested successfully here.

No new code defect blocking the tested 12B configuration was found. The 4B output-quality failures and CPU latency are recorded limitations. DEV publication and owner-posted X announcement are closed in the publication record. Inline DEV video with sound/controls remains deferred, not a release blocker. Both branch mock-test CI runs and the separate pinned Quillgrain job passed; those are separate from this live evidence.

The initial workflow configuration-only run `40079863718` failed before inference because a job-level environment value used the unavailable `runner` context; the corrected workflow used a Linux temporary model path. No model response was fabricated for that attempt.

After collecting both experiments, the workflow was changed to manual-only with a 12B default and an explicit 4B comparison choice. This avoids starting model downloads on ordinary branch pushes. Evidence run IDs above refer to the earlier push-triggered experiment revisions.

RC follow-up: this evidence branch has been integrated into main and `0.3.0rc1` metadata/facts/archive checks are prepared in the [candidate record](0.3.0-release-candidate.md). Earlier dev0/main state statements above describe the experiment boundary. Final release/tag remains held.
