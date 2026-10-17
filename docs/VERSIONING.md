# Versioning

FaustCoder uses [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
and records changes in [CHANGELOG.md](../CHANGELOG.md) using
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Current state

There are no releases and no tags. The first tag is `v0.1.0`, created only when
there is something releasable: the V0.1 FOUNDATION acceptance in spec §12 is met
(another operator can reproduce compiler receipts and baseline metrics from a
clean checkout).

## What a version covers

The repository version covers code, schemas and the release manifest. Before
1.0.0, a MINOR bump may contain breaking changes; say so in the changelog.

| Change | Bump (from 1.0.0) |
|---|---|
| Incompatible change to a contract in `schemas/`, the inference API, or a state-machine transition table | MAJOR |
| New backward-compatible capability, contract field, or task-suite addition | MINOR |
| Fix with no contract change | PATCH |

Milestones in spec §12 map to versions: V0.1 to `v0.1.0`, V0.2 to `v0.2.0`,
and so on. A milestone tag is created only when its PASS criterion is met.

Other versioned things keep their own version and do not follow the repository
tag:

- Each spec has a `Version` line in its header.
- The constitution has its own version (`.specify/memory/constitution.md`).
- Each schema carries `schema_version`.
- Datasets, splits, runs and models are identified by content digest, never by
  a version string or alias (spec §3).

## Release steps

1. Move entries from `Unreleased` to a new `## [x.y.z] - YYYY-MM-DD` section.
2. Merge that change through a pull request.
3. Create an annotated tag `vX.Y.Z` on the merge commit and a GitHub release.
   Model releases also need the full gate in spec §15.
