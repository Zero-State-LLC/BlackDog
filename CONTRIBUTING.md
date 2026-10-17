# Contributing

Read the canonical specification before implementation. Submit contract changes with schema tests and ADRs. Never add training data without provenance and rights review. Never modify frozen evaluation holdouts. Do not commit model weights, credentials, raw restricted datasets or generated receipts containing personal data.

Every implementation PR must identify requirements, dependencies, acceptance tests, evidence paths, failure dispositions and any security impact.

## Workflow

- Work on a branch and open a pull request against `main`. Direct pushes and force-pushes to `main` are blocked; merges are squash-only.
- Follow the Spec Kit order in the [constitution](.specify/memory/constitution.md): spec, plan, tasks, then code.
- Fill in the pull request template checklist and add an entry under `Unreleased` in [CHANGELOG.md](CHANGELOG.md).
- Install the hooks once: `pipx install pre-commit && pre-commit install`. They run gitleaks, markdownlint and basic file checks.
- Required CI checks: `structure`, `spec-kit`, `markdownlint`, `links`, `gitleaks` and `actionlint`.
- Report vulnerabilities privately; see [SECURITY.md](SECURITY.md). Everyone follows the [Code of Conduct](CODE_OF_CONDUCT.md).
