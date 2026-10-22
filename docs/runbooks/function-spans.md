# Verified function spans

Admitted T06 function units require an externally reviewed range manifest.
This is extraction infrastructure, not a Faust parser, new rights clearance,
H2/H3/FLOOR qualification or T07 freeze. `TOKEN_FLOOR=40` remains provisional.
The existing pinned inventory has no approved production span manifest from #89.

## Review boundary

A reviewer must verify complete function/overload boundaries, associated notices,
and dependency safety against the exact pinned source. The manifest digest must
be approved independently of the supplied document. A caller who replaces both
can select different bytes: checksums verify the reviewed selection, not the
reviewer's judgment, signature, or semantic completeness. Reviewer text is audit
metadata, not authenticated authorization. Do not derive ranges automatically
from `rights_policy.slice_library` metadata or use its starting line/body hash
as proof of complete syntax boundaries.

Dependencies are not expanded or granted rights. Unsupported/ambiguous functions
stay unqualified. Same-blob non-cleared units still quarantine all cleared units
in that blob, even if a proposed range appears disjoint. Rejected comparison
blobs remain whole and are never emitted. This deliberately does not unlock the
mixed-license library corpus; a separately reviewed policy change would be needed.

## Manifest and invocation

The [JSON schema](../../specs/001-faustcoder/contracts/function-spans.schema.json)
defines `function-spans.v1`. Top-level fields are `schema_version`,
`inventory_digest`, `notice_digest`, `reviewer`, and `spans`.
Inventory/notice digests use the existing content-digest rules, including their
entry-order and timestamp handling. The span manifest pin is
`sha256_prefixed(canonical_bytes(document))`; unlike inventory entries, its array
order is content-bearing. Use a stable order when preparing a reviewed manifest.

Each span names the existing `unit_id`, `repo`, `pin`, `path`, `blob_sha`, exact
`function` key (including any overload suffix), `start_byte`, `end_byte`, and
`sha256` of the selected original bytes. Ranges are zero-based, end-exclusive,
on original bytes, before BOM/line-ending/whitespace normalization. Byte ranges
can select separate definitions on the same line. A range must be nonempty,
in bounds, on UTF-8 boundaries, and disjoint from other selected ranges in the
same source identity. Duplicate/unknown units and unknown fields are refused.
Exactly one range is required per admitted function, including sealed functions;
whole-file and already excluded units must not have span rows.

```text
faustcoder-snapshot --inventory INVENTORY --notice NOTICES \
  --fetcher fixture --fixture-root LOCAL_SOURCES --store NEW_STORE \
  --created-at TIMESTAMP --function-spans REVIEWED_SPANS \
  --function-spans-digest APPROVED_CANONICAL_SHA256
```

The Python API accepts `function_spans` and `function_spans_digest` in
`compile_snapshot`. Structural/pin/identity validation precedes fetching.
Source Git-hash and selected-byte validation precede storage; compilation of the
snapshot must succeed before `commit_snapshot` writes any artifact. Invalid spans
abort the run. The CLI returns usage error 2 for span errors and acquisition error
3 for source hash mismatches. File-only snapshots need no manifest.

Examples and manifest unit rows record `function_span`, including the manifest
pin, identity, byte offsets and selected digest. `original_sha256` continues to
hash the full source blob; `normalized_sha256` hashes only extracted normalized
text. Thus range/manifest changes affect downstream evidence. Existing receipts
are not rewritten. Rejected/holdout text is not emitted as an Example.

## Regression acceptance

Check multiline and adjacent functions, overload identities, quoted delimiters,
CRLF handling, UTF-8 boundaries, missing/duplicate/overlapping ranges, stale pins,
wrong content hashes, notice binding, deterministic replay and CLI refusal before
storage. Retain whole-blob mixed-rights quarantine and holdout exclusion tests.
These checks do not qualify a real corpus or change `split_frozen=false`.

## Merged-main verification and receipts

PR [#89](https://github.com/Zero-State-LLC/BlackDog/pull/89) merged as `adee7ae`
on 2026-10-20 PT (2026-10-21 UTC). Codex review completed with no findings;
all eight CI checks passed. The [full CI suite](https://github.com/Zero-State-LLC/BlackDog/actions/runs/39545602844)
reported **668 passed, 63 warnings in 181.59s** using existing authorized runner
sudo operations. No new sudo operations were introduced.

The subsequent fresh SSH session on spark-af42 activated `~/BlackDog` on merged
main and passed **143 regressions in 16.70s**: function spans, snapshots,
normalization, near-dedup, floor protocol, CLI, rights/policy and schemas.
The tests check exact selection and provenance, invalid-range refusal, existing
quarantine, sealed exclusion, provisional floor 40 and `split_frozen=false`.
The tracked checkout stayed clean; all **92,319** existing files/symlinks in the
preservation baseline were unchanged. No sudo, workload stops, environment
installation or model downloads were used for that Spark verification.

| Evidence | Location |
|---|---|
| Merged-main Spark verification | `/home/delphi/blackdog-function-spans-main-verification/` |
| Earlier isolated Spark implementation validation (143 passed in 16.93s) | `/home/delphi/blackdog-function-spans-validation/` |
| Backup of earlier implementation validation | `outputs/blackdog-function-spans/validation-receipts/` in the outer local workspace |
| Full CI log | `outputs/blackdog-function-spans/pr89-ci/spec-structure.log` in the outer local workspace |

Merged-main receipts include `README.md`, `environment.txt`, `tests.log`,
`git-status.txt`, `preserve.py`, `preservation-before.json`,
`preservation-after.json` and `SHA256SUMS`; all seven checksum entries passed.
The earlier portable backup has 16 verified checksum entries and final source
hashes; it is distinct from the newer merged-main verification, which is retained
on Spark. All these artifacts remain outside Git and `/tmp`.

## Partial production candidate (unapproved)

On spark-af42 at main `84c51a3`, an initial candidate was prepared from directly
inspected pinned source definitions. **It is incomplete and unapproved; it cannot
be used for a production snapshot.** No independent reviewer or trusted digest
approval is claimed, and no inventory rights or exclusions were changed.

| Measure | Result |
|---|---|
| Inventory function rows | 1,784 |
| Function units admitted by existing inventory checks | 965 across 27 blobs |
| Local source verification | All 27 blobs match their pinned Git hashes |
| Proposed ranges | 7; 958 admitted-unit spans still missing |
| JSON schema and selected identity/range/hash/UTF-8 checks | Pass for the diagnostic subset only |
| Full-inventory manifest validation | Expected refusal: `missing function spans` |
| Preservation | 93,754 existing files/symlinks unchanged; 13 receipt checksums passed |

The seven proposals are `routes.lib` functions `cross`, `cross2`, `crossNM`,
`crossnn`, `crossn1`, `cross1n`, and the `version.lib` constant `version`.
Existing eligibility is **LGPL-2.1-or-later, train-only** for all seven; no
evaluation or redistribution rights are added. `cross2` depends on `cross`;
`crossnn`, `crossn1` and `cross1n` depend on `crossNM`. These definitions have
separate spans, not implicit dependency expansion. Other selected expressions
use Faust built-ins/constants; dependency and parameter-domain qualification
still require independent review.

Ranges use explicit inspected definition literals, not automatic parsing or
rights-metadata slice hashes. An initial uniqueness check caught `cross2` in a
documentation example; the actual definition and its trailing comment resolve
that ambiguity. A notice serialization error was corrected before final receipt
generation. Neither failure changed admission rules or repository files.

During initial candidate preparation, no compilation, rendering, semantic task
validation, family/leakage audit rerun,
DatasetSnapshot or signed SplitManifest was produced. These small routing and
constant definitions do not qualify complex bodies or overload groups, and their
representativeness for training remains a separate question. Full manifest
coverage cannot be bypassed by treating the subset diagnostic as admission or
trimming the pinned inventory to make this candidate pass.

### Candidate receipts

Spark directory: `/home/delphi/blackdog-function-span-candidate-20261021/`.
This directory is outside Git and `/tmp`; no off-host backup is claimed here.

- `function-spans.candidate.json`: seven unapproved ranges.
- `candidate-digest.UNAPPROVED.json`: canonical integrity digest, explicitly not an approved production pin.
- `coverage-ledger.json`: all 965 admitted function units, notice/rights metadata and review gaps.
- `source-verification.json`: 27 source-blob checks; `inventory-exclusions.json`: retained exclusion dispositions.
- `summary.json`, `REPORT.md`, `prepare.py`, `prepare.log`: result, limitations and reproduction procedure.
- `preserve.py`, `preservation-before.json`, `preservation-after.json`, `git-status.txt`: preservation evidence.
- `SHA256SUMS`: all 13 listed receipt files verified.

The preparation script contains the small explicit source selections; keep it
with the private receipts, not in Git or published documentation. No sudo,
workload stops, environment changes, model downloads or GPU work were used.
`TOKEN_FLOOR=40` remains provisional and T07 remains unfrozen.

## Seven-span compiler and signal validation

A subsequent bounded review on spark-af42 at main `fc1990e` confirmed the seven
selected definitions and tested explicit dependency closure. **28 positive
compiler/signal runs and five negative controls passed.** This does not approve
the candidate manifest or change its then seven-of-965 coverage; 958 spans were
missing and full-inventory validation refused incomplete coverage.

| Check | Result and scope |
|---|---|
| Boundaries and hashes | All seven contain complete definitions with no neighboring definition; pinned blob and selected-byte hashes match |
| Dependencies | `cross2` requires `cross`; `crossnn`, `crossn1`, `cross1n` require `crossNM`; other selected expressions use Faust built-ins/constants |
| Positive runs | 14 cases at each of 44.1/48 kHz, 144,000 frames, block size 64; all 28 passed |
| Routing oracle | Distinct impulse weights `(i+1)/16` and explicit expected channel permutations, followed by zeros |
| Version oracle | Constant tuple `(2, 80, 0)` |
| Negative controls | Four omitted-dependency compiler refusals; one wrong-permutation reference rejection |
| Preservation | 94,487 existing files/symlinks unchanged; original candidate receipts unchanged; 146 new receipt checksum entries verified |

Tested cases: `cross(1)`, `cross(3)`, `cross(5)`, `cross2`, `crossNM(2,3)`,
`crossNM(3,2)`, `crossNM(1,1)`, `crossnn(1)`, `crossnn(2)`, `crossn1(1)`,
`crossn1(3)`, `cross1n(1)`, `cross1n(3)` and `version`. Wrappers contain the exact
selected definitions, explicitly supplied dependencies and diagnostic scaffolding;
there is no fallback to full-library imports. `cross2` includes its inline
comment; the version range excludes only its trailing PATCH explanation.

The version tuple is not audio. Its diagnostic profile explicitly sets
`reject_dc`, `reject_clipping` and `reject_silence` to false to permit the expected
constants and zero channel. Reference and finite-output checks remain enabled;
routing cases retain default checks. Numeric tolerances, goldens and sandbox
controls are unchanged. These are CPU sandboxed WASM diagnostics, not reward or
promotion acceptance, native C++ validation or cross-architecture qualification.

### Validation receipts and limits

New receipts: `/home/delphi/blackdog-seven-span-review-20261021/`, outside Git and
`/tmp`. `REPORT.md`, `summary.json`, `boundary-dependency-review.json`,
`validate.py`, `validation.log`, per-case DSP/compiler/diagnostic/signal/reference
specifications, negative controls, preservation records, `candidate-checksums.txt`
and `SHA256SUMS` record the run. Reference arrays are reproducible from compact
specifications. Private source wrappers remain with the receipts; no off-host
backup is claimed. The original candidate directory above was not rewritten.

This is Codex direct source review and execution, not independent production
review or trusted-digest approval. Positive compile-time integer channel counts
listed above are tested; zero, negative, fractional, dynamic and very large
counts are unqualified. The sample does not qualify complex bodies, overloads,
broader dependencies, general DSP task coverage or training representativeness.
Existing train-only rights and whole-blob quarantine remain unchanged.

At this stage, the next steps were independent boundary/dependency/rights review,
preparing the remaining 958 ranges, and extending real-corpus/task qualification
and family/leakage checks.
H2/H3/FLOOR, independent development and holdout coverage, and signed T07 freeze
remain open. `TOKEN_FLOOR=40` stays provisional; T07 stays unfrozen. No dataset
snapshot, training run or stack pin was created. No sudo, workload stops,
package changes, downloads or GPU work occurred.

## Expanded 13-span candidate and batch-two validation

On spark-af42 at main `84dd8413e8e988038569295cf3083942584e3d2c`
(2026-10-21 UTC), a separate candidate added six `routes.lib` definitions:
`interleave@232`, `interleave@233`, `_comparatorAsc`, `_comparatorDes`,
`_comparator@430` and `_comparator@431`. **13 of 965 admitted function units
now have proposed spans; 952 remain missing.** The original seven rows are
unchanged. All 13 retain existing **LGPL-2.1-or-later, train-only** eligibility;
none has independent production approval.

| Check | Result and scope |
|---|---|
| Boundaries and identity | Exact complete clauses inspected against pinned source; blob and selected-byte hashes, schema, selected-unit identities, nonoverlap and UTF-8 checks pass |
| Overloads and dependencies | Both interleave clauses compile together in source order using built-ins; comparator dispatch clauses compile together with explicit ascending/descending helpers using min/max |
| Positive runs | 13 cases at each of 44.1/48 kHz: all 26 sandboxed WASM compiler/signal runs passed, with 144,000 frames and block size 64 |
| Negative controls | Two omitted-helper compiler refusals and two incorrect-output reference rejections passed |
| Full inventory | Correctly refuses `missing function spans`; the subset is not production admission |
| Preservation | 95,355 existing files/symlinks unchanged; prior candidate and seven-span receipt checksums pass; all 139 new receipt checksum entries verified |

Interleave cases cover `(1,2)`, `(2,2)`, `(2,3)`, `(3,2)` and `(3,1)`, with
independently specified transpose permutations and distinct impulse weights.
Ascending/descending helpers and dispatch modes 0/1 each cover mixed-sign and
equal inputs against sorted references. Wrappers use exact extracted clauses
and explicit dependencies, without whole-library import fallback. Individual
clauses are not claimed to be complete standalone overload groups. All default
signal checks, numeric tolerances, goldens and sandbox controls were retained.
The earlier seven-span compiler/signal tests were preserved, not rerun; their
bytes were revalidated in the combined manifest.

### Batch-two receipts and qualification limits

Receipts: `/home/delphi/blackdog-span-batch2-20261021/`, outside Git and `/tmp`.

- `function-spans.candidate.json` and `candidate-digest.UNAPPROVED.json`: combined candidate and integrity digest, not a trusted production pin.
- `batch-review.json`, `coverage-ledger.json`: boundaries, dependencies, rights and all 965 units' coverage status.
- `REPORT.md`, `summary.json`, `validate.py`, `validation.log`: results and reproducible procedure.
- Per-case DSP/compiler/diagnostic/signal/reference files and negative controls: bounded execution evidence.
- `preservation-before.json`, `preservation-after.json`, `preserve.py`, `git-status.txt`: preservation evidence.
- `original-candidate-checksums.txt`, `seven-span-checksums.txt`, `SHA256SUMS`, `checksum-verification.txt`: prior and new receipt verification.

Private source wrappers stay with receipts; no off-host backup is claimed.
These finite impulse diagnostics do not qualify all streams or dimensions,
zero/negative/fractional/dynamic/very large dimensions, dispatch modes outside
0/1, NaN/infinity sorting, full bitonic networks, native C++ or cross-architecture
behavior. Codex direct review is not independent production approval. Broader
real-corpus/task representativeness and family/leakage qualification remain open.

No production snapshot, signed split, training run or stack pin was created.
No sudo, workload stops, environment changes, downloads or GPU work occurred.
`TOKEN_FLOOR=40` remains provisional and T07 remains unfrozen.

## Remaining T06 and T07 gates

1. Independently review the 13 proposals and prepare the remaining 952 ranges
   before seeking approval of a complete production manifest against exact
   pinned source, complete function/overload boundaries, notices and dependency
   safety. Qualify extraction on real corpus units; no production ranges are
   approved by #89. Preserve same-blob non-cleared quarantine and record rejected
   or ambiguous units instead of using disjoint spans to bypass it.
2. Complete T06 H2 canonical-stream and H3 Unicode regressions on the shipping
   extraction/dedup path. Keep the raw stream and the documented policy boundaries;
   see the [canonical tasks](../../specs/001-faustcoder/tasks.md).
3. Run the §25 FLOOR protocol only after H2/H3, using fixed ground truth and the
   same shipping streams. `TOKEN_FLOOR=40` remains provisional; extraction tests
   do not accept a floor or close H2/H3/FLOOR.
4. Resolve [T07 freeze blockers](t07-candidate-audit.md#freeze-blockers-and-acceptance):
   missing pinned sources, independent development coverage, DSP/task semantics,
   independently authored sealed holdout custody and exclusion screening, and
   signed-freeze implementation/rejection tests. T01 remains a dependency.
   T07 is unfrozen; no DatasetSnapshot or signed SplitManifest was created.
   Any permitted provisional-floor freeze still needs the documented leakage
   caveat, scheduled recheck and later removal receipts. T08 baselines follow a
   qualified freeze; this update does not authorize training or a stack pin.
