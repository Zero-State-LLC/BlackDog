# JSON Schemas

These files are byte-for-byte copies of the JSON Schemas listed in the
[spec 001 contracts](../specs/001-faustcoder/contracts/README.md).

| Item | Value |
|---|---|
| Source path | `specs/001-faustcoder/contracts/*.schema.json` |
| Source commit | `fcc391e5b4360f594309f1e99cc1b8ac9baeaf9c` |
| Copied | 2026-10-17 |

`inference-api.md` is not a JSON Schema and is not copied. `$id` values are
unchanged, so each schema keeps the identity of its spec contract.

Do not edit a file here without editing the source file in the same change.
`tests/test_schemas.py` fails when any `*.schema.json` pair differs.
`compiler-receipt.schema.json` is schema_version 0.3.2 (ADR-0005); the copy
matches `contracts/`.

## Canonical payload

The artifact id is the SHA-256 of the canonical payload. The normative
rules are the module docstring of
[faustcoder/canonical.py](../faustcoder/canonical.py). Summary:

- Encode the `payload` object as JSON with keys sorted by Unicode code
  point, UTF-8, and no insignificant whitespace.
- `artifact_id` is the lowercase hexadecimal SHA-256 digest (64 characters).
- `content_digest` is `sha256:` followed by that digest.
- The file stored on disk is the canonical encoding of the whole envelope.
- A second put of the same id succeeds only when those bytes match.

## Reading of the spec

[data-model.md](../specs/001-faustcoder/data-model.md) says `artifact_id` is
a stable id and `content_digest` is `sha256:<hex>` of the canonical payload.
It does not say which bytes are hashed, or that the two fields are the same
digest. The envelope schema checks the shape of `content_digest` and does
not require it to equal the payload. This store uses the minimal reading:

- The hashed bytes are the canonical encoding of the `payload` field only.
- `artifact_id` is that digest in hex. `content_digest` is the prefixed form.
- Parents are content digests, because the envelope schema requires
  `sha256:<hex>`. A parent must already be stored. A link that reaches the
  new artifact, including a self-parent, is rejected.

Envelope fields other than `payload` are not covered by `content_digest`.
`artifact_id` stays the payload hash: data-model.md does not say otherwise,
and the envelope schema rejects additional properties, so the integrity
digest is not an envelope field. The store writes
`<artifact_id>.envelope_digest` beside the object. That file is
`sha256:` plus the hex SHA-256 of the canonical envelope bytes, with
nothing excluded. `get` and `list` recompute it and reject a mismatch,
including a rewrite of `producer`, `created_at`, `parents`,
`schema_version`, `artifact_id`, `content_digest` or `payload` that
leaves the sidecar unchanged.
