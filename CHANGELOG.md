# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
See [docs/VERSIONING.md](docs/VERSIONING.md).

## [Unreleased]

### Added

- T03b follow-up: the native sandbox also masks `<binary>/../share/faust`, `<binary>/../lib/faust`, and every directory `faust --libdir`, `--dspdir`, `--includedir`, `--archdir` and `--pathslist` print, except the hashed private copy. A library planted beside a copied `faust` binary cannot be imported. CI installs Faust 2.88.0 so that check runs.

- T03b follow-up: creating the share lock directory happens while the in-process lock's release is armed, so a failed `mkdir` cannot stick the lock. The native sandbox masks `/usr/share/faust` and `/usr/local/share/faust` when they exist. Faust cannot fall back to them after `-I`.

- T03b follow-up: the in-process share lock and the file lock share one 30-second deadline. A directory at the lock path raises `SandboxError`. Native compiles hash a private copy of the share and pass that copy as `-I`.

- T03b follow-up: waiting for the faustlibraries share lock is bounded. A timeout raises `SandboxError` instead of blocking a cold publish. The lock file is opened with `O_NOFOLLOW` and a symlink is refused. After a tamper refusal, delete `share-<commit>` and re-stage; the harness does not delete that tree itself.

- T06: normalize pinned Faust sources, cluster exact and near-duplicates, and write a deterministic `DedupManifest`. Admission calls the T05 rights guard and consumes `corpus/rights-inventory.v1.json` and `corpus/notice-manifest.v1.json` by content digest. A unit is admitted only when `(repo, commit, path, function, blob_sha)` is a cleared T05 unit, and the ingested bytes must hash to that blob id before normalization. T06 does not execute `rights_cleared` or `rights_rejected`. Near-duplicate families intersect rights, and a family that mixes licenses is quarantined. Texts under 40 tokens use a character n-gram fallback. Impulse eval exclusion uses the entry id and the path. Rejected and `needs_human` blobs are fetched for near-duplicate clustering and are never emitted; a cleared near-copy or a verbatim excerpt of one is `needs-human`. Four upstream originals copied by syfala on 2024-02-13 stay cleared only when every non-cleared family member is that entry's recorded copy. A cleared file that vendors a shorter rejected blob, plus its own padding, is `needs-human`. Reverse containment quarantines a cleared file when at least half of a rejected text's shingles sit in it, including after one edited literal per statement or when those statements are interleaved with the cleared file's own code. `TOKEN_FLOOR` is the single length constant for the Jaccard minimum and the verbatim run (currently 40). The manifest records `token_floor_status: provisional`. That value is not an accepted clearance policy; the short-kernel measurement is in [docs/analysis/t06-short-kernel-floor.md](docs/analysis/t06-short-kernel-floor.md). `generated_at` is not part of the snapshot digest. Corpus compile checks stay behind the T03b gate and default off. See [docs/runbooks/t06-normalize-dedup.md](docs/runbooks/t06-normalize-dedup.md).
- T04: offline DSP signal harness. faustwasm renders impulse, sine and noise at 44.1 and 48 kHz inside the T03 sandbox. Receipts record hash-stable RMS, peak, NaN/Inf/denormal counts and spectral bands, and compare a candidate to a reference within an absolute tolerance. Known-good fixtures include legal delayed feedback. Library imports stay with T03b. CPU wall time is stored only for a promotion candidate.

- T03b follow-up: a multi-file `source_sha256` includes the selected entry path. Publishing the shared library tree takes a process-wide file lock and does not delete a live tree. A failed network canary raises `SandboxError` instead of an `internal` receipt. The worker hashes the bytes it writes into `/usr/share/faust` and that hash has to match the Python share hash.

- T03b follow-up: `environment_digest` records the resolved path and sha256 of the `unshare` binary that runs, including the system binary when `FAUSTCODER_UNSHARE` is unset. A swapped wrapper changes the digest before the network canary runs.

- T03b follow-up: `environment_digest` binds the tree mounted at `/usr/share/faust`. The share is re-hashed on every reuse, the worker hashes the bytes it mounts, and a mismatch is refused before a receipt. `FAUSTCODER_UNSHARE`, when set, must be an absolute root-owned regular file that group and others cannot write; the compile process checks that the network namespace has only `lo` and that a connect fails. Recorded exclusions store both the raw sha256 and the T06-normalized sha256 (six of the eight raw hashes differ). A `CompilerExclusion` of model output is a failure when rewards land. The `faustcoder` group must contain only the harness user. ADR-0006 is Accepted 2026-10-17 (Danny).

- T03b: stage faustlibraries commit `2edec0537f53` into `/usr/share/faust` before every compile, and point the native 2.88.0 cross-check at the same tree. `environment_digest` includes the commit and the canonical lib-tree sha256. Sibling `.dsp` imports are staged. Node `--stack-size=8192` is the bound for `2dKirchhoffThinPlate.dsp`. Five faust-stk `ffunction` files, and three multi-file `fastpow2` files, are recorded exclusions. The Spark runbook installs root-owned `/opt/faustcoder/bin/fc-unshare` (mode 0750, group `faustcoder`) instead of an AppArmor profile on `node`. ADR-0006 (Accepted 2026-10-17, Danny) grades source-attributable failures at `parse_error` once the grader changes land; reward behavior is unchanged until then.

- T05: source rights inventory (`corpus/rights-inventory.v1.json`), the notice manifest (`corpus/notice-manifest.v1.json`), and the dataset `rights_cleared` / `rights_rejected` transitions. A clearance requires a matching notice row, a pinned commit, and a named reviewer when the evidence is inferred. Exclusion receipts carry a reason and do not copy program text.

- T03 follow-up: the compiler runs as the calling user (`unshare --net --map-current-user`, `CapEff` 0). Every receipt reuses the embedded libfaust pin. `environment_digest` covers the bundled faustlibraries triplet and the runtime bytes. Receipts are stored and looked up by reproducible digest. CompilerReceipt `diagnostic_class` adds `unbound_symbol`, `resource_limit` and `internal` (spec 0.3.2, ADR-0005, Danny yes 2026-10-17 1:13 PM PT).

- T03: sandboxed Node.js worker around libfaust from faustwasm 0.19.0. Python drives it with no network, a wall-clock timeout, a resident-memory cap and an output-size cap, and stores a CompilerReceipt in the T02 artifact store. The native Faust 2.88.0 cross-check runs only when that binary is already installed.
- T09: DGX Spark feasibility study, bounded environment probe, and the training-machine `env_verified` transition. CI covers the state machine with a mocked Spark fingerprint. On-hardware throughput is not measured in this change.

- T02 follow-up: envelope-integrity sidecar verified on read, and a pytest job in the existing spec-check workflow.

- T02: content-addressed filesystem artifact store (`faustcoder/`) and top-level `schemas/` copied from `specs/001-faustcoder/contracts/`. Pytest covers schema validation, digest determinism, immutability, tamper detection and parent-cycle rejection.

- ADR-0004: target lanes and Faust tooling reuse; `target-receipt.schema.json`.

- Starter package: README, CONTRIBUTING, KANBAN, spec 001, ADR-0001 and the spec-structure CI check (#1).
- Spec Kit artifacts for spec 001: constitution, plan, tasks, data model, contracts, research, checklists and explicit state machines (#2).
- Repository hygiene: security policy, code of conduct, CODEOWNERS, issue and PR templates, changelog, versioning policy, EditorConfig, pre-commit with gitleaks.
- CI: markdownlint, link check, gitleaks secret scan, Spec Kit structure check, actionlint and Dependabot for GitHub Actions.
- Training-path research and ADR-0002 (PROPOSED): adapt an open base code model through P0 corpus and harness, P1 continued pretraining, P2 SFT and P3 compiler-feedback RL.

### Changed

- Spec 001 to 0.3.4 (ADR-0006, Danny 2026-10-17 4:11 PM PT, A2 extended 4:28 PM PT): the R-005 reward ladder incorporates A1–A7 by reference to the ADR. A7's 1%, 500-sample and 2× numbers are provisional. Reward code keeps ADR-0005 behavior until the grader PR lands. See spec §23.

- ADR-0006 accepted 2026-10-17 4:11 PM PT (Danny): source-attributable failures graded at `parse_error`; environment and harness errors (reproducible infrastructure failures and deterministic harness defects) ungraded and quarantined; A1–A7 (A7 numbers provisional). A2 extended 2026-10-17 4:28 PM PT (Danny): untraced timeouts and crashes stay ungraded and quarantined until triage attributes them to the source. Docs only; reward behavior stays on the ADR-0005 table until the grader changes land.

- T04: the signal comparison keeps an exact head and a coarse whole-render check (per-block RMS and band energies). Impulse references are built at 144000 frames and trimmed to the decay plus a margin. The tail gate scans the whole reference, and a default impulse render uses that reference or the cap instead of a fixed 2048. A `reward_graded` receipt forces non-finite rejection and a reference, signs the trimmed reference (`head_frames` equals that length), and keeps coarse checks to the samples past it. An impulse reference with `max_frames` below the 144000 block-aligned cap raises `ValueError` and does not raise the cap. `thresholds.reward_graded` is always stored and is part of the reproducible digest. The renderer uses the shared netns canary. A failure raises `SandboxError` and writes no receipt. The compiler canary raises before render. `harness_digest` and the receipt metrics include `unshare_path` and `unshare_sha256`.

- Spec 001 to 0.3.3 (D-013, Danny yes 2026-10-17 1:04 PM PT): STK-4.3 is other-permissive with a required notice; bare BSD is not redistributed; vendored copies are deduped by content hash and not cleared; faustlibraries is sliced per function; mixed licenses take the strictest; CC-TODO comments are stripped; GPL and LGPL stay training-only, with a near-duplicate output filter proposed for T06 and T07. See spec §22.
- Spec 001 to 0.3.1 (Danny yes 2026-10-17 12:54 PM PT): for v0.2, R-001 is satisfied by cited external DGX Spark benchmarks plus a per-machine environment fingerprint receipt. On-hardware throughput is deferred to T10 on the dedicated Spark cleared of other workloads before training.
- T09 probe: the default memory cap is that dedicated machine's MemTotal minus an 8 GiB OS margin, and cannot exceed 120 GiB. The 96 GiB shared-machine ceiling is withdrawn. 7.6B full-parameter AdamW stays a no-go on 128 GB unified memory.

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
