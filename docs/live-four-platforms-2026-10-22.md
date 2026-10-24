# Four-platform headless run: 22 October 2026

The `0.3.0.dev0` working implementation completed real local generation for Telegram, X, DEV and GitHub using `gemma4:12b`. Five model requests completed in one CLI invocation with stdin closed (`DEVNULL`), exit code 0, elapsed wall time **123.258 s**. No PatchPitch web server or browser was started. These are draft-generation results, not four remote platform deliveries or a performance benchmark.

## Observed catalog

The [catalog and research notes](x-catalog.md) contain 11 tags drawn from 19 linked public posts by 15 authors. The [ledger](../examples/headless/x-observations-2026-10-22.json) records indexed-primary versus mirror access, original links, derived post dates and editorial relevance. Counts were recomputed from unique posts/authors. One finance promotion was excluded from relevance counts. No engagement, click, impression or hashtag-lift figures were invented.

This is a small historical sample reviewed today, not an authenticated recent-X search. Some primary pages returned 403/cache misses; mirror authenticity and real audience response remain unverified. The 30-day review expiry is separate from historical post dates.

## Generation and retained evidence

| Target | Accepted model requests | Observed model time |
| --- | --- | --- |
| English X single | Topic plan + writing | 4.267 s + 5.748 s |
| Russian Telegram | Writing | 29.898 s |
| English DEV | Writing with local Quillgrain pack | 50.410 s |
| English GitHub notes | Writing | 31.910 s |

All returned model identities were `gemma4:12b`. Runtime source fingerprint: `5883ae708e8ff6a677ccf3608493a78419a8f5297f43445130fe6338283e5493`. The observed installed model digest was `6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b`, separately from returned response identity.

DEV used directly compiled Quillgrain 0.1.0rc3, register `engineering_article`, build `529afc9f879e904939299f135cf1c33e609a7f028cbaad4dc3af04bf903ca9d3`. The original designed pack has no author corpus: this establishes integration behavior, not author-voice fidelity. The reusable [public example](../examples/headless/all-four.toml) uses the normal `clear` preset; the actual local job adds this explicit Quillgrain binding.

The first complete invocation retained an X failure, `X_LENGTH_EXCEEDED`; the other three targets finished. The model followed a 150–200-character approximation instead of its smaller six-tag budget. The request now omits that conflicting instruction and supplies a JSON-schema prose ceiling based on the smallest complete-card budget, including the last CTA. Weighted Unicode/URL validation still checks the actual return. A fresh run passed; the first inputs and failed response were preserved.

Selected X tags were `#DevTools #LocalAI #LLM #Ollama #OpenSource #Automation`. After explicit editorial shortening and a development-status disclosure, the complete post measured **245/280** using `x-estimate-v1`. Six distinct selected tags and the exact CTA remained intact. This is a conservative estimate; an X composer/API acceptance check has not been performed.

The DEV article was generated through PatchPitch, then explicitly edited for headings, plain language, development status and the distinction between local generation and account delivery. Telegram received a correction to a mistranslated remote draft and clearer limits. GitHub notes retain the development label. This is agent editing; owner review remains pending.

CLI validation passed for all four edited publication files, and campaign session export passed. Repeat `run` and explicit `resume`, both with stdin closed and network connections/UI imports blocked, returned the existing successful run with zero connection attempts and no UI modules loaded. Hash checks confirmed that all five attempt files, four original results and eight publication files were unchanged by those two operations.

The change-specific regression suites passed **75 tests**: 66 campaign/social tests and nine package/delivery/Git-voice tests. The earlier complete offline suite passed 325 tests before this additional length regression; it was not rerun for this observation record. `git diff --check` found no whitespace errors.

## Local outputs and delivery state

**Historical state below is as of 22 October.** The later reviewed article was published to DEV on 23 October; the owner posted its X announcement and chose to skip Telegram. See the [publication closeout](publication-closeout-2026-10-23.md) for final links, media and provenance.

The final local run is under `artifacts/cli-0.3.0/four-platform-final/patchpitch-four-platforms/0d3e246e0a8a2ac07bd9/`. It includes frozen inputs, all raw responses, selected-tag decisions, edited publication files, validation, exported session, a copied research ledger/catalog, `editorial-review.json`, `original-hashes.json` and `headless-reuse-proof.json`. The earlier partially failed run is under `artifacts/cli-0.3.0/four-platform-live/`; it was not overwritten.

The DEV article and its metadata remain **local and unpublished** (`published=false`). `PATCHPITCH_DEV_API_KEY` was absent from process, user and machine environments. No remote draft was created, and no delivery receipt was fabricated. A key is needed only for the explicit account-write step, not for article generation. [DEV's own API documentation](https://dev.to/devteam/documenting-the-forem-v1-api-15ck) describes generating a key under [Settings → Extensions](https://dev.to/settings/extensions).

No public Telegram/X/GitHub post or release was created. Remote DEV round-trip, final X acceptance, owner editorial approval and a public 0.3.0 release remain separate evidence gates.
