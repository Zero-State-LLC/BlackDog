# Security policy

## Supported versions

BlackDog is pre-release. No version is supported yet; security fixes land on
`main`. This section changes when v0.1.0 ships (see
[docs/VERSIONING.md](docs/VERSIONING.md)).

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately through
[GitHub private vulnerability reporting](https://github.com/Zero-State-LLC/BlackDog/security/advisories/new).

Include the affected file or component, steps to reproduce and the impact you
expect. You get an acknowledgement when the report is triaged. Please allow time
for a fix before disclosure.

## In scope

- Sandbox escapes from the Faust compiler or signal-test workers (spec R-013).
- Ways for generated code, prompts or retrieved examples to execute outside the sandbox.
- Dataset poisoning, benchmark or holdout leakage, and artifact-integrity bypasses (spec §11).
- Secrets, credentials or restricted data committed to this repository.

## Data that must never be committed

Licensed or restricted datasets, training material without a rights review,
model weights and checkpoints, `.env` files and credentials, and receipts that
contain personal data. `.gitignore`, the gitleaks pre-commit hook, GitHub secret
scanning with push protection, and the `secret-scan` CI job enforce part of this.
If something slips through, report it privately as above; do not try to remove
it with a force-push.
