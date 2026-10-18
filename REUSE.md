# Provenance

PatchPitch was implemented locally on 2026-10-18 from the owner's handoff.
New work: Python app and local Ollama adapter, strict response contract, source
selection/inspection, editing/export UI, checks, examples and capture/render scripts.

BeautifulRepo's [release-note guide](https://github.com/drevendev/BeautifulRepo/blob/master/guides/release-notes.md)
(blob `af293b4a1080832bab1ffb6686b7f84ffdfb4b97`) informed the editorial choice to
write for readers and preserve limitations. Its public changelog supplied the
paraphrased documentation example; no guide, parser or implementation was copied.
The source's MIT notice is preserved in THIRD_PARTY_NOTICES.md.

Whipstack was not accessible through the connected GitHub account (404). No
private code, logs, launcher or telemetry were read or copied. Placeholder
validation is a small original regular-expression check, motivated by SPEC's
readiness rule and the handoff's AgencyFoundry idea; it is not a port of that module.
HungryCrab and Devostasis are not dependencies and were not modified.

Gemma weights remain separate under Google's terms. Ollama and FFmpeg are local
development tools kept in ignored `.tools/`; their binaries are not part of the
source distribution. Model, runtime and package notices remain with those downloads.
No inherited repositories, schedules or running fleet were changed.

The owner approved the MIT source license and public repository on 2026-10-18.
Idle Fantasy Shop example facts are selected/paraphrased from the owner's public
0.12 devlog. This is not a copied game implementation or an independent code audit.
Optional narration uses Kokoro-82M v1.0 (Apache-2.0), via kokoro-onnx (MIT).
Weights/voices and generated audio are not bundled in the source repository.
