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

### Teacher outputs (D-006r2)

- Provenance: Danny yes 2026-10-16 22:25 PT. Supersedes the training-data part of D-006
  (Danny yes 2026-10-16 22:20 PT).
- Training targets may come only from models whose outputs carry no
  restriction on training use. Default: `deepseek/deepseek-v4.1-flash`
  (MIT) via OpenRouter.
- Opus outputs are never stored as training targets or in released data.
  Opus may review, grade and judge evaluations only.
- Each synthetic item records its teacher model id in its `SourceRecord`, so
  items from a disallowed source can be found and removed. INFERRED.

### D-007: per-function licensing (Danny yes 2026-10-16 23:39 PT)

- Refines D-004. A license is resolved per function where a library declares
  one per function (faustlibraries), and per file otherwise.
- Header-less example files inherit their repository's license. For the Faust
  repository that is LGPL-2.1-or-later, so those files are training-only.
- AGPL stays excluded.

### D-011: upstream contributions (Danny yes 2026-10-16 23:39 PT)

- Fixes to the Faust compiler or libraries found while building FaustCoder
  may be contributed upstream under the upstream LGPL license. They are not
  under the Zero State license.

### Target SDKs and tools (ADR-0004, INFERRED, not legal advice)

- CLAP SDK, clap-wrapper and the VST 3 SDK (3.8 and later) are MIT. JUCE
  (AGPLv3 or commercial) is not used by default.
- `pluginval` (GPL-3.0) and `lv2lint` (Artistic-2.0) run as separate tools and
  are never linked into or shipped with FaustCoder output.
- Faust architecture files compiled into a generated plugin carry their own
  license terms; a plugin release would need its own review (out of scope, §2).

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
  only. (Confirmed by D-007 for header-less files.) AGPL, MPL and other copyleft licenses are not covered by the approval
  and stay excluded until decided.
- Resolved (Danny yes 2026-10-16 22:25 PT): the repository was transferred to the Zero-State-LLC
  organization, so ownership matches the proprietary license. It stays public
  for now (ORG-001, Danny 2026-10-16 22:32 PT), revisitable later.
- Section 4 of the proprietary license bars AI-training use of covered
  material without Zero State's authorization; Zero State's own use is
  unaffected.
