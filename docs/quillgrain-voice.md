# Quillgrain voice and Russian Telegram drafts

The optional local integration consumes a checked `voice-bundle.json`. Ordinary
presets still work without Quillgrain. Install a trusted local Quillgrain engine
checkout that includes `quillgrain.consumer` into the same Python environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e PATH_TO_QUILLGRAIN_ENGINE
```

In Quillgrain, compile the desired pack and bindings with:

```text
qg pack build --pack PATH_TO_PACK --register maker_announcement --language ru --target patchpitch --host ollama --tag delivery.vivid --tag social.telegram --max-chars 14000 --out NEW_EXPORT
```

For a local author-example pool, also pass `--tag examples.chosen --example-pool
examples.chosen`. Without explicit pool selection, untagged Common examples remain
eligible. Review the export's selection/omission report before loading it.

A full author post can supply ready-made jokes even when the prompt prohibits
copying. Prefer a curated delivery excerpt without distinctive punchlines or
personal-plan passages when the local model keeps recycling them. Record excerpt
provenance and distinguish a synthetic neutral `before` from an owner-written
`after`. This is editorial selection, not proof of author voice, and not an
automatic semantic joke remover. Keep the complete source separately and private.

1. Open **Quillgrain · author voice** and select the export's `voice-bundle.json`.
   Import checks the schema, hashes, matching lock, scope and local-host permission.
   Loading chooses the declared language/channel; it never starts generation.
2. Review product, audience and selected facts. Choose **Русский**, **Telegram post**
   and **Quillgrain voice**. Compiled voice replaces generic tone presets. The old
   1,200-character prose sample is kept separate and is not combined with it.
3. Optionally provide allowed tags and enable Auto tags. Telegram allows up to five
   selected suggestions and a total 4,096-codepoint text/CTA/tag budget. This is the
   application's conservative text budget, not a Telegram API conformance claim.
4. Confirm facts and generate with local Gemma. Review meaning, style and historical
   versus current release claims. Russian lexical checks are partial, not a semantic
   verifier. A candidate profile does not guarantee an authentic author voice.
5. Edit and copy/download the text. Newlines and Markdown markers remain intact;
   paste does not automatically create Telegram entities. Apply rich formatting
   and custom emoji manually. Nothing is published by PatchPitch.
6. **Download session** deliberately includes the private voice snapshot, raw model
   responses and current edits. Keep it private. **Open session** restores these
   without generating. Product-profile exports contain product basics, not voice.

Each generation retains its build/pack identity and effective style assembly hash.

RU Telegram with an imported voice uses a native Russian author prompt instead of
the generic release/benefit preset. All selected rules and examples retain their
priorities; examples also retain authorship and role. Style/reference data is
separate from task facts. Gemma 4 uses direct generation with the selected source
IDs before prose; ordinary drafts keep their existing generation path. Request hash,
adapter ID and thinking flag are recorded with the result. Eight-word verbatim
reference passages are rejected unless the same passage is in selected task facts.
This narrow guard cannot detect a paraphrased or very short recycled joke: review
the draft, and never treat samples as a phrase bank. Raw failures are retained for
manual inspection, without automatic cleanup or a hidden regeneration.

Changing the selected voice affects future requests only. Single-card X regeneration
uses that result's saved input/voice snapshot, not a newer profile loaded elsewhere.
Removing voice returns to ordinary presets; existing drafts retain their history.
Invalid imports leave the current profile and edited draft unchanged. Language or
channel mismatch blocks that voice generation instead of silently falling back.

No corpus scanning, private-repository access, cloud inference, automatic profile
refresh or feedback training is performed. Session data stays in the tab until
explicit local export; private voice content is not sent to Sentry. Retain failed
attempts and distinguish structural tests from real model runs and owner judgment.
