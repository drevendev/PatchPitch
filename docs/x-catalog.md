# Observed X catalog: 22 October 2026

[Catalog](../examples/headless/x-catalog-2026-10-22.json) and [observation ledger](../examples/headless/x-observations-2026-10-22.json) are real, manually reviewed public observations, separate from the synthetic test fixtures. The ledger contains 19 distinct linked posts from 15 authors; 18 posts were judged relevant to developers describing their own tools or workflows. One trading promotion is retained as a negative sample. The catalog contains 11 tags with at least one relevant observation each.

The sample is purposive and historical. It establishes observed topical use, **not hashtag effectiveness or current popularity**. Search results exposed primary X post snippets and public TwStalker snapshots. Direct X requests often returned 403/cache misses; access method and original post links are recorded per observation. Mirror content has not been authenticated against X. Relative mirror timestamps were discarded; dates decoded from status IDs are explicitly labelled as derived. No engagement, click, impression or causal lift figures were imported.

`observed_at` is the time the indexed evidence was reviewed. `window_days=366` describes the historical sampling window; it does not mean continuous monitoring. `max_age_days=30` requires a new evidence review after 21 November 2026. It does not make an old post recent. The `local:` evidence references point to the sibling ledger. Keep that ledger with the catalog when copying it or archiving a campaign.

| Tag | Relevant / reviewed posts | Relevant authors | Appropriate context |
| --- | --- | --- | --- |
| #DevTools | 6 / 6 | 4 | Developer tooling, CLI workflows |
| #BuildInPublic | 6 / 6 | 6 | Actual development progress |
| #OpenSource | 6 / 7 | 4 | Explicitly open-source project |
| #LocalAI | 6 / 6 | 4 | Local model inference |
| #Ollama | 4 / 4 | 2 | Actual Ollama integration |
| #Automation | 3 / 4 | 3 | Unattended or automated workflow |
| #CLI | 2 / 2 | 1 | Command-line use |
| #LLM | 2 / 2 | 1 | Language-model workflow |
| #Python | 1 / 2 | 1 | Python implementation or usage |
| #PythonDevelopment | 1 / 1 | 1 | Python development; narrow evidence |
| #Markdown | 1 / 1 | 1 | Explicit Markdown conversion/output |

`audience_fit` is an editorial relevance rating, not a traffic score. Sparse evidence and repeated authors remain visible. Selection requires matching words in the cited facts and the planned topic, audience compatibility and a current evidence review. It ranks those criteria deterministically, then reserves space for exactly six selected tags before writing. Final meaning still needs review; lexical matching alone cannot establish it. There is no unconditional six-tag default set.

Run all four formats without a browser:

```text
python -m patchpitch run --job examples/headless/all-four.toml --out-root artifacts/campaigns --json
```

The command generates local publication files. DEV account delivery remains a separate explicit `deliver --channel dev --mode draft` command with `PATCHPITCH_DEV_API_KEY`. No Telegram, X or GitHub publication is performed by this job.
