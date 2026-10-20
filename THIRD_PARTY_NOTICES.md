# BeautifulRepo

The BeautifulRepo documentation example paraphrases a public changelog entry.
Editorial guidance was consulted. Source: https://github.com/drevendev/BeautifulRepo

MIT License

Copyright (c) 2026 Dreven

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

# Optional local narration tooling

Kokoro-82M v1.0 weights: Apache License 2.0, model card and terms at
https://huggingface.co/hexgrad/Kokoro-82M . Standard `af_heart`/`af_bella` voices
are from that model distribution. They are used for local demo narration, not
cloning the owner's voice. Model files and audio are excluded from this repository.

kokoro-onnx runtime: MIT, https://github.com/thewh1teagle/kokoro-onnx .
Its dependencies retain their own licenses with their installed distributions;
optional tooling does not add an audio dependency to the PatchPitch application.

# Bundled interface fonts

Manrope — Copyright 2018 The Manrope Project Authors.
Newsreader — Copyright 2020 The Newsreader Project Authors.
Both fonts are distributed under the SIL Open Font License 1.1.
Original font files, full license texts and source URLs/checksums are retained in
`patchpitch/static/fonts/`. Sources: https://github.com/google/fonts/tree/main/ofl/manrope
and https://github.com/productiontype/Newsreader . No external font request is made
when using the application.

# Optional local Gemma 4 model

The locally downloaded `gemma4:12b` distribution exposes the Apache License 2.0
in its Ollama model metadata. Weights are not bundled with PatchPitch or covered
by PatchPitch's MIT license. Model source: https://ollama.com/library/gemma4:12b .
# X length reference (0.2.0)

The original `x-estimate-v1` helpers use the published twitter-text v3 weight
ranges and 23-character URL convention as reference data. They do not bundle
twitter-text code or claim conformance. The official short URL cases are checked
alongside original ASCII/Unicode/emoji/boundary fixtures; compound emoji and long
URLs are deliberately estimated conservatively. Source, inspected 2026-10-20:
https://github.com/twitter/twitter-text/blob/master/config/v3.json and
https://github.com/twitter/twitter-text/blob/master/conformance/validate.yml .
The upstream repository is Apache-2.0 licensed; its full implementation is not
included. The app always requires checking the final text in X.
