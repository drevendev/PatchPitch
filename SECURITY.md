# Security policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting:
<https://github.com/drevendev/PatchPitch/security/advisories/new>.
Do not open a public issue or pull request for a security problem, and do not post
exploit details, secrets, session files or private source text anywhere public.

A useful report names the affected file or feature, the commit, the steps to
reproduce and what an attacker gains. The maintainer,
[@drevendev](https://github.com/drevendev), triages reports on a best-effort basis.
No response time is promised.

## What counts as a vulnerability here

PatchPitch is a local tool. The app listens on `127.0.0.1`, sends model requests only
to Ollama at `127.0.0.1:11434`, and sends diagnostics only when you configure a Sentry
DSN. A way around any of these is in scope:

- a fact pack, session file, Git repository or model response that runs code or reads
  files the user did not select;
- the Git importer running hooks, external diff or textconv commands, or changing the
  checkout;
- private input (notes, drafts, diffs, session contents) reaching a network service,
  including through the Sentry allowlist;
- the app answering on a non-loopback interface by default.

Model output quality, the recorded public demo's content and third-party services you
choose to configure are out of scope.

## Supported versions

There are no tagged releases yet. Fixes land on `main`.
