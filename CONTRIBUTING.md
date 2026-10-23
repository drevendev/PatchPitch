# Contributing to PatchPitch

Issues and pull requests are welcome. PatchPitch is maintained by one person, who
reviews them when possible; no response time is promised.

## Before you start

Open an issue first for larger changes. Changes that add hosted inference, accounts,
publishing endpoints or automatic posting change the product's boundaries, so discuss
them before writing code. Keep one topic per pull request.

## Set up and run the checks

Follow [Try it](README.md#try-it) to run the app. For the tests, install the
development dependencies and the Playwright browser:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-dev.lock
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) '.tools\browsers'
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
```

On Linux or macOS, use `.venv/bin/python`. The browser download is the only large
step. Unit, API and browser tests use labelled **MOCK** model responses, so no model or
Ollama is needed. Real-model checks are optional and separate: `scripts/doctor.py --live`
and `scripts/evaluate.py --live`.

## Pull requests

- Describe the user-visible change and add an entry under an `## Unreleased` heading
  in [CHANGELOG.md](CHANGELOG.md).
- Never commit secrets or private material: a Sentry DSN, `.env` files, session files,
  Git review JSON or anything under `artifacts/`.
- Say what you tested, including whether a real model was used.

## Security

Report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md).
