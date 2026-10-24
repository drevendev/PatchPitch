# Automatic campaigns without a browser

Available in the **0.3.0.dev0 working implementation**. This is a development build; the full release gates are in the [specification](0.3.0-spec.md).

## Install and run

Python 3.11+ is required. Install the package from this checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-build-isolation .
```

The CLI needs Pydantic and Sentry SDK; FastAPI, uvicorn and Playwright are not imported. Install `.[ui]` when you also want the studio. An existing Ollama installation and explicitly installed model are needed for inference. The CLI never downloads a model or starts a server.

```powershell
$env:PATCHPITCH_MODEL = 'gemma4:12b'
$env:PATCHPITCH_SENTRY_DSN = ''
python -m patchpitch run --job examples/headless/campaign.toml --out-root artifacts/campaigns --plan --json
python -m patchpitch run --job examples/headless/campaign.toml --out-root artifacts/campaigns --json
```

The installed `patchpitch` command is equivalent to `python -m patchpitch`. Outside this checkout, use an absolute job path. Paths inside the job are relative to the job file. The included example produces Russian Telegram, English DEV and GitHub development drafts. It describes local code, not a released version.

`--plan` does no inference, writes no campaign and does not contact platforms. It checks local inputs and dependencies and gives a conservative request count. Actual model availability and model-produced topics are checked during execution.

`--out-root` derives a campaign directory from the complete input/runtime digest. A scheduler can invoke the same command repeatedly: unchanged inputs reuse the completed run, while changed inputs get another directory. For a fixed destination use `--out RUN_DIRECTORY`; changed inputs in that directory return `RUN_INPUT_MISMATCH`.

For Windows Task Scheduler, use the absolute virtual-environment `python.exe` as the executable and these arguments:

```text
-m patchpitch run --job C:/PATH/TO/campaign.toml --out-root C:/PATH/TO/campaigns --json
```

No desktop session, stdin prompts or browser is needed. A [self-hosted Actions example](../examples/headless/self-hosted-workflow.yml) is included. Prepare the local runtime/model first; a hosted runner without Ollama is not an inference environment.

## Files, edits and recovery

The JSON summary on stdout gives the run directory and per-target status. Progress goes to stderr. Exit codes are 0 success/no changes, 2 input/configuration, 3 dependency/model availability, 4 inference/validation/partial failure, 5 delivery. A partial failure preserves successful targets.

The run has `manifest.json`, immutable input `snapshot.json`, `sources.json`, `attempts/`, `voices/` and `outputs/<target-id>/`. Every model attempt is checkpointed before the request. A completed response can be recovered even if the process stops before export finishes. OS locks prevent competing writes and concurrent model calls between CLI and studio. The [implementation record](0.3.0-implementation.md) distinguishes offline checks, failed live attempts and accepted local drafts.

Edit the designated publication files:

| Target | Editable files |
| --- | --- |
| Telegram | `draft.md` |
| X | `P01.txt`, `P02.txt`, …; ordering is retained by the generated plan |
| DEV | `article.md` for body/CTA; `article.json` for title, description and tags |
| GitHub | `release-notes.md` |

`original.json` and `attempts/` retain model responses; leave them intact. `current.json` is refreshed by validation. Meaning and facts still need editorial review. For X, text edits must keep six selected tags and their relevant topic words. Length is checked on the full post, including tags, URLs and CTA.

```text
patchpitch resume --run RUN_DIRECTORY --json
patchpitch validate --run RUN_DIRECTORY --json
patchpitch export --run RUN_DIRECTORY --kind session --out RUN_DIRECTORY/session.json --json
```

Resume is an explicit retry of unfinished/failed steps within `max_model_requests`; accepted steps are reused. It uses the frozen snapshot and requires the same runtime/model configuration. It preserves publication edits. Use a new run for changed configuration or source data. Open the exported session through **Save and open → Open session JSON** in the studio; this performs no inference and restores all completed formats. Sessions and runs can contain private voice/examples and source code; keep the complete run local.

## Git without confirmation clicks

Replace `[source]` with:

```toml
[source]
kind = "git_range"
repository = "PATH_TO_LOCAL_REPOSITORY"
base = "BASE_COMMIT_OR_REF"
head = "HEAD"
files = ["src/example.py"]
candidate_selection = "all_valid_candidates"
```

The job explicitly authorizes the selected committed diffs. All existing Git bounds/omissions apply; working-tree edits remain excluded and dirty state is disclosed. Model extraction is sequential and checkpointed. Selected candidates stay `machine_selected_unreviewed`. An equal base/head returns `no_changes` without inference.

An oversized pool is saved to `facts/candidates.json`, then returns `FACT_BUDGET_EXCEEDED`. To choose a subset without re-extracting, create a selection JSON with the exact `preview_sha256`, `candidate_sha256`, `selected_ids` such as `B00F00`, and `candidates_file` pointing to that saved pool (relative to the selection file). Set `candidate_selection="selection_file"` and `selection_file="selection.json"` in a new job/run. Both source and candidate digests must match.

## Six meaningful X tags

The [four-platform example](../examples/headless/all-four.toml) includes a [dated observed catalog and its research ledger](x-catalog.md). Review its sampling limits and refresh the observations when they expire. You can also enable the commented X target in the basic example after supplying your own catalog. New studio generation uses this policy by default; the explicit legacy checkbox preserves old workflows. Old sessions open without rewriting their text.

```text
patchpitch schema --kind hashtags --out hashtag-catalog.schema.json --json
```

The catalog has schema `patchpitch.hashtag-catalog/v1`, `id`, `version`, `max_age_days` (default 30) and `tags`. Every candidate supplies a `tag`, `languages`, `keywords`, `audience_keywords`, optional `excluded_keywords`, an editorial `audience_fit` of 1–3 and an `evidence` list. Each observation has `kind` (`own_analytics` or `public_sample`), a source URL or `local:` import reference, timezone-aware `observed_at`, `window_days`, `sample_size`, `relevant_posts` and optional authors/engagements/clicks. Unknown metrics remain absent/null.

The topic plan uses cited facts. Selection requires matching topic words in both the plan and cited facts, matching audience, and fresh observations. Ranking is deterministic: topic matches, editorial audience fit, observed sample relevance density, observation time, author count, lexical tie-break. Likes and clicks are not mixed into a made-up reach score. Each post gets exactly six tags. `hashtag_decisions.json` preserves selections, observations, scores and rejected candidates.

No fake trends or pre-filled performance metrics are supplied. If six relevant observed tags are unavailable, X fails with `HASHTAGS_INSUFFICIENT_EVIDENCE`; other targets can finish. The automated match is lexical, not proof of meaning or guaranteed reach. `x-estimate-v1` remains a conservative length estimate; check final text in X.

## Quillgrain

Install the trusted local **Quillgrain 0.1.0rc3** engine into the same environment; the compiler is optional and is not vendored/downloaded by PatchPitch:

```text
python -m pip install -e PATH_TO_TRUSTED_QUILLGRAIN_CHECKOUT
patchpitch voice build --config examples/headless/voice.toml --language ru --format telegram --out NEW_VOICE_DIRECTORY --json
```

Edit the [voice configuration](../examples/headless/voice.toml) first. In a job, name that same configuration under `[voices.NAME]` and put `voice="NAME"` on a target; omit `style`. `mode="local_pack"` compiles the named pack directly. `mode="bundle"` loads a checked bundle from `path`. Specify its register explicitly when it differs from `maker_announcement`.

Compiler settings include bindings, overlays, tags, example_pool and budget. Telegram uses `social.telegram`, X `social.x`, and DEV/GitHub `social.longform`. Language/register/channel, lock/build and permissions are checked. Every generation keeps its own snapshot. Choosing another profile affects future requests; rewriting an existing post uses its saved input. Style examples remain separate from task facts. See [voice details and limitations](quillgrain-voice.md).

## DEV draft delivery

Generating and editing a local DEV article needs no DEV account key. A key is required only to save that article into your DEV account through the explicit delivery command. In [DEV Settings → Extensions](https://dev.to/settings/extensions), find **DEV Community API Keys**, enter a name such as `PatchPitch`, and click **Generate API Key**. This is [DEV's documented authentication method](https://dev.to/devteam/documenting-the-forem-v1-api-15ck). Set the value in the environment of the process running `deliver`; `.env` is not read automatically. Do not put the value in a job, source control or a chat message.

Review/edit the generated article first, then invoke delivery explicitly:

Articles are generated as sections and individual paragraphs; the application formats Markdown without rewriting their words. Code examples are inserted verbatim from selected source snippets. This avoids relying on the model to recreate working configuration or paragraph separators; original structured responses are retained.

```text
patchpitch deliver --run RUN_DIRECTORY --channel dev --mode draft --json
```

Set `PATCHPITCH_DEV_API_KEY` in the process environment. Only article title, description, body, tags, AI disclosure and `published=false` are sent; run snapshots, raw responses and voice bundles are excluded. Tags are sent as an array. `article.json` can declare `ai_disclosure_level` as `no_ai`, `some_ai` or `fully_autonomous`; generated articles default to `fully_autonomous`. Repeat uses the saved article ID, verifies it is still your draft and updates that draft when content changed. A published article is never reverted to draft by this command. [Forem API contract](https://developers.forem.com/api/v1).

If a write response is lost, `delivery.json` records an uncertain outcome and blocks another blind POST. Find the actual draft and reconcile with `--existing-id ID`; its ownership and submitted content must match. New receipts retain the exact outgoing article payload (never the key or voice bundle), allowing reconciliation even after later local edits. When the owned-article API omits AI disclosure, the adapter compares all observable content and re-sends the explicit desired disclosure with a PUT to that same draft. A returned disclosure must match; missing data is not treated as `fully_autonomous`. Legacy receipts can reconcile from unchanged local publication files; restore the original files if their saved payload cannot be reconstructed. A definite rejection such as HTTP 401 remains a failed delivery and permits an explicit retry after correcting credentials. No public publication or baseline advancement occurs through draft delivery. A real DEV account round-trip is a separate release check; offline adapter tests do not establish it.

## Integration CI

The separate `quillgrain` job checks out engine revision `8af17f979c0ad20163bec5fd247279a7a6f5addf`, verifies version `0.1.0rc3`, runs voice/browser/Git-campaign checks and rejects skipped tests. The normal suite still verifies that ordinary workflows work without the optional engine. CI inference is mocked; this does not replace a Linux live-model run.

## Verified Linux live configuration

The [24 October Linux live run](linux-live-2026-10-24.md) completed all four targets from a clean installed package with real `gemma4:12b` inference and no UI. On the tested CPU runner, set `PATCHPITCH_TIMEOUT=600`: the DEV request took 497.921 seconds, exceeding the ordinary 420-second default. Model digest, inputs, exact timings, raw evidence and the rejected Gemma 3 4B comparison are in the record. Do not assume equivalent results from an arbitrary smaller model.

```sh
export PATCHPITCH_MODEL=gemma4:12b
export PATCHPITCH_TIMEOUT=600
export PATCHPITCH_SENTRY_DSN=''
python -m patchpitch run --job /absolute/checkout/examples/headless/all-four.toml --out-root /absolute/campaigns --json </dev/null
```

Start the prepared local Ollama server and install the selected model explicitly beforehand. The optional `.github/workflows/linux-live.yml` acceptance harness provisions an ephemeral runner/model separately and saves public-input evidence; it is manual-only after the experiment to avoid downloading a multi-GB model on ordinary pushes. Generation never calls a publisher.
