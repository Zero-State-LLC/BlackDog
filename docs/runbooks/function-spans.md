# Verified function spans

Admitted T06 function units require an externally reviewed range manifest.
This is extraction infrastructure, not a Faust parser, new rights clearance,
H2/H3/FLOOR qualification or T07 freeze. `TOKEN_FLOOR=40` remains provisional.
The existing pinned inventory has no approved span manifest supplied by this PR.

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
