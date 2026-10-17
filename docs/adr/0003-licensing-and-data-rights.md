# ADR-0003: Licensing and data rights

Status: ACCEPTED

- Date: 2026-10-16
- Provenance: Danny yes 2026-10-16 22:20 PT
- Decides: repository license (issue #20) and spec D-004
- Related: [ADR-0002](0002-training-path.md), [spec §14](../../specs/001-faustcoder/spec.md#14-open-decisions)

## Decision

### Repository license (split)

- `specs/` and `docs/`, including ADRs, are under Apache-2.0
  ([LICENSE-APACHE](../../LICENSE-APACHE), with copies in `specs/LICENSE` and
  `docs/LICENSE`).
- Code, model weights and data are under the Zero State Proprietary License
  1.0 ([LICENSE](../../LICENSE)), copied verbatim from Zero-State-LLC/Patch-Hive.
  It is the default for every path not under `specs/` or `docs/`.
- The scope is written down in [NOTICE](../../NOTICE) and the README.

### D-004: training-corpus rights

- Allowlist: MIT, BSD (all variants), Apache-2.0 and other permissive
  licenses.
- GPL code may be used for training only. It is never redistributed: not
  committed to this repository and not included in any released dataset.
- Unlicensed code (no license file or declaration) is excluded.

## Consequences

- Every `SourceRecord` carries a license claim; `RightsRecord.eligible_for`
  is `train` only for GPL sources and `train, eval, redistribute` only for
  allowlisted sources. INFERRED.
- Released data cards list only allowlisted sources. Model cards state that
  GPL code was used in training. INFERRED.
- Specs and docs can be reused under Apache-2.0; code and weights cannot be
  reused without written permission from Zero State.

## Interpretation notes for owner confirmation

These are INFERRED readings, not part of the approval. Not legal advice.

- "Other permissive" is read as ISC, Zlib, BSL-1.0, 0BSD, MIT-0, CC0-1.0,
  Unlicense and STK-4.3 (the STK license used in faustlibraries).
- LGPL, including the Faust library exception, is treated like GPL: training
  only. AGPL, MPL and other copyleft licenses are not covered by the approval
  and stay excluded until decided.
- The proprietary license names Zero State LLC as owner while the repository
  sits on the personal account `scrimshawlife-ctrl`; transfer to the
  Zero-State-LLC organization if ownership should match.
- Section 4 of the proprietary license bars AI-training use of covered
  material without Zero State's authorization; Zero State's own use is
  unaffected.
