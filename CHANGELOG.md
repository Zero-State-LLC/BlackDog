# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [docs/VERSIONING.md](docs/VERSIONING.md).

## [Unreleased]

### Added

- ADR-0004: target lanes and Faust tooling reuse; `target-receipt.schema.json`.

- Starter package: README, CONTRIBUTING, KANBAN, spec 001, ADR-0001 and the spec-structure CI check (#1).
- Spec Kit artifacts for spec 001: constitution, plan, tasks, data model, contracts, research, checklists and explicit state machines (#2).
- Repository hygiene: security policy, code of conduct, CODEOWNERS, issue and PR templates, changelog, versioning policy, EditorConfig, pre-commit with gitleaks.
- CI: markdownlint, link check, gitleaks secret scan, Spec Kit structure check, actionlint and Dependabot for GitHub Actions.
- Training-path research and ADR-0002 (PROPOSED): adapt an open base code model through P0 corpus and harness, P1 continued pretraining, P2 SFT and P3 compiler-feedback RL.

### Changed

- D-012 VST3 route evidence (Danny yes 2026-10-16 23:56 PT): `faust2clap` + clap-wrapper is OBSERVED to build and validate on Linux with known bugs (research F26, F27; ADR-0004); fallback `faust2juce` after a JUCE licence decision, second fallback a DPF spike; plugin-lane smoke CI with strict CLAP validation expected to fail.
- Spec 001 to 0.3.0 (ADR-0004, Danny yes 2026-10-16 23:39 PT): reuse Faust tooling (faustwasm compiler and renderer, impulse-test references, compiler JSON instead of a custom parser); task taxonomy by faustlibraries category, task type and target; per-function licensing (D-007); runtimes D-003r2; new target lanes for language backends, plugins (CLAP, VST3, LV2), embedded boards (Daisy, Teensy 4.x) and a V0.5-FPGA milestone with an F0 spike; new `TARGET_CHECKED` candidate state and TargetReceipt contract; tasks T17 to T22.
- Research F10 corrected: the Faust compiler is LGPL-2.1-or-later, not GPL.

- Project board moved to the public [org project 29](https://github.com/orgs/Zero-State-LLC/projects/29); KANBAN.md link updated. Repository and board are public for now (ORG-001 resolved, revisitable).

- Repository transferred to the Zero-State-LLC organization; repository URLs updated. It stays public.
- Secret scan job `gitleaks` now runs the checksum-verified gitleaks 8.30.1 CLI; gitleaks-action requires a paid license key for organization repositories.
- D-006 superseded by D-006r2: open-weight `deepseek/deepseek-v4.1-flash` via OpenRouter generates training data; Opus is used only for review, grading and eval judging.

- Licensing: split license accepted (ADR-0003). Apache-2.0 for `specs/` and `docs/`, Zero State Proprietary License 1.0 for everything else; LICENSE, LICENSE-APACHE, NOTICE and per-directory license files added; README and CONTRIBUTING updated (closes #20).
- Decisions D-003 (44.1 and 48 kHz), D-004 (corpus allowlist, GPL training-only) and D-006 (Opus via OpenRouter, per-run spend cap) accepted; spec §18 decision log added.

- Spec 001 to 0.2.0: small-model shortlist, per-phase training method, phase gates and flagged slowdowns (§17).

[Unreleased]: https://github.com/Zero-State-LLC/FaustCoder/commits/main
