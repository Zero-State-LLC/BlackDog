# Contributing

Read the canonical specification before implementation. Submit contract changes with schema tests and ADRs. Never add training data without provenance and rights review. Never modify frozen evaluation holdouts. Do not commit model weights, credentials, raw restricted datasets or generated receipts containing personal data.

BlackDog was formerly named FaustCoder. The Python package, CLI entry points and environment variables still use the `faustcoder` name; that is expected.

New collaborators: start with the [collaborator handoff](docs/HANDOFF.md) for current status and open work.

## Licensing of contributions

- Contributions to `specs/` and `docs/` (including ADRs) are licensed under
  [Apache-2.0](LICENSE-APACHE).
- Contributions anywhere else, including code, scripts, CI, model weights and
  data, are licensed under the [Zero State Proprietary License](LICENSE).
  Zero State may require a contributor agreement before accepting them
  (LICENSE section 6).
- Training data follows ADR-0003: MIT, BSD, Apache or other permissive
  sources only; GPL code for training only and never committed or released;
  unlicensed code excluded.

## Development setup

These steps mirror the `pytest` job in [`.github/workflows/spec-check.yml`](.github/workflows/spec-check.yml), which is the reference. Requirements: Linux, Python 3.11 or newer (CI uses 3.12), Node.js 22 with npm, `curl`, and unprivileged user namespaces (`unshare --net --map-current-user -- true` must succeed).

```bash
git clone https://github.com/Zero-State-LLC/BlackDog.git
cd BlackDog
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]"

# Pinned faustwasm 0.19.0 for the sandboxed compiler worker
(cd faust/worker && npm ci --ignore-scripts)

# Pinned, checksum-verified Faust trees (downloaded to gitignored paths)
./scripts/fetch-faustlibraries.sh
./scripts/fetch-faust-examples.sh

# Check the compiler network namespace
unshare --net --map-current-user -- true
```

Some tests also need the native Faust 2.88.0 compiler. `./scripts/install-faust-2.88.0.sh` installs it system-wide and uses `sudo`; read the script and the [compiler harness runbook](docs/runbooks/compiler-harness.md) first. On DGX Spark machines follow [Verified Spark setup](docs/runbooks/spark-local-setup.md) instead, and never change the host-wide user-namespace sysctl there.

Without the two fetch scripts, `pip install` plus `pytest` still runs, but the compiler, signal and some snapshot tests fail with a message that names the missing step.

## Running tests and checks

```bash
python -m pytest                      # full suite (pyproject sets -q and --strict-markers)
python -m pytest tests/test_store.py  # one file
./scripts/check-spec-kit.sh           # Spec Kit structure (CI job: spec-kit)
```

Lint and secret scanning run through pre-commit (gitleaks, markdownlint-cli2 and basic file checks). Install the hooks once, then run them on everything before you push:

```bash
pipx install pre-commit
pre-commit install
pre-commit run --all-files
```

There is no Python linter or formatter configured yet. Follow [`.editorconfig`](.editorconfig).

## Required CI checks

A pull request into `main` cannot merge until these checks pass: `structure`, `spec-kit`, `markdownlint`, `links`, `gitleaks`, `actionlint` and `pytest`. The `contracts` job (JSON Schema metaschema check) also runs on every pull request.

Pull requests from forks run the same workflows with a read-only token and no repository secrets. A maintainer must approve the first workflow run for a first-time contributor.

## Branches, commits and pull requests

- Work on a branch and open a pull request against `main`. Direct pushes and force-pushes to `main` are blocked; merges are squash-only and the branch must be up to date with `main`.
- Name branches by type, for example `feat/...`, `fix/...`, `docs/...`, `spec/...`, `test/...`, `ci/...` or `chore/...`.
- Use a Conventional Commits style pull request title, for example `fix(reward): ...` or `docs: ...`. The squash commit takes the title.
- Fill in the [pull request template](.github/pull_request_template.md) checklist and add an entry under `Unreleased` in [CHANGELOG.md](CHANGELOG.md).
- Resolve every review conversation before merge; the ruleset requires it.
- Label unestablished facts OBSERVED, INFERRED or SPECULATIVE, as the constitution requires.

### Requirements for implementation PRs

Every implementation PR must identify requirements, dependencies, acceptance tests, evidence paths, failure dispositions and any security impact.

## Specs, ADRs and the constitution

- Follow the Spec Kit order in the [constitution](.specify/memory/constitution.md): spec, plan, tasks, then code. Implementation does not start until `spec.md` and `plan.md` exist for the area being changed.
- The canonical spec is [specs/001-faustcoder/spec.md](specs/001-faustcoder/spec.md), with `plan.md`, `tasks.md` and JSON Schema contracts beside it. The backlog is [KANBAN.md](KANBAN.md).
- To propose a change to a spec, contract, state machine, ADR or the constitution, open a "Spec change" issue, then a pull request that changes the spec text.
- Contract changes ship with schema tests and an ADR in [docs/adr/](docs/adr/), numbered after the last one. Stateful features need a `From | Event | Guard | To | Effect` transition table; `./scripts/check-spec-kit.sh` enforces it.
- Constitution amendments bump its version and are recorded in `CHANGELOG.md`.
- Owner decisions are recorded under [docs/decisions/](docs/decisions/).

## Data, holdouts and secrets

- Private and sealed holdout tasks are never committed to this repository, in any branch, issue, pull request, fixture or log. Only their SHA-256 checksums are referenced.
- Do not paste holdout content, keys or credentials into issues, pull requests, CI logs or agent tools.
- `.gitignore` blocks common data, checkpoint, weight, `.env` and holdout paths. It is a safety net, not a permission: check `git status` before every commit.
- If a secret or restricted file is committed, do not force-push to remove it. Report it privately as described in [SECURITY.md](SECURITY.md).

## Conduct and security

Report vulnerabilities privately; see [SECURITY.md](SECURITY.md). Everyone follows the [Code of Conduct](CODE_OF_CONDUCT.md).
