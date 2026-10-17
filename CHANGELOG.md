# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [docs/VERSIONING.md](docs/VERSIONING.md).

## [Unreleased]

### Added

- Starter package: README, CONTRIBUTING, KANBAN, spec 001, ADR-0001 and the spec-structure CI check (#1).
- Spec Kit artifacts for spec 001: constitution, plan, tasks, data model, contracts, research, checklists and explicit state machines (#2).
- Repository hygiene: security policy, code of conduct, CODEOWNERS, issue and PR templates, changelog, versioning policy, EditorConfig, pre-commit with gitleaks.
- CI: markdownlint, link check, gitleaks secret scan, Spec Kit structure check, actionlint and Dependabot for GitHub Actions.
- Training-path research and ADR-0002 (PROPOSED): adapt an open base code model through P0 corpus and harness, P1 continued pretraining, P2 SFT and P3 compiler-feedback RL.

### Changed

- Spec 001 to 0.2.0: small-model shortlist, per-phase training method, phase gates and flagged slowdowns (§17).

[Unreleased]: https://github.com/scrimshawlife-ctrl/FaustCoder/commits/main
