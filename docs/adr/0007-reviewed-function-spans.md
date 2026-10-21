# ADR-0007: Reviewed byte spans for T06 function extraction

Status: IMPLEMENTED in [#89](https://github.com/Zero-State-LLC/BlackDog/pull/89),
merged as `adee7ae`. Code review completed with no findings; full CI passed
668 tests. This records implementation review, not approval of production ranges
or closure of the corpus qualification gates.

## Decision

Use an externally reviewed, independently digest-pinned `function-spans.v1`
manifest to bind exact UTF-8 byte ranges to admitted inventory function identities
and inventory/notice digests. Require complete coverage of admitted functions;
refuse stale, ambiguous or overlapping entries. Normalize selected bytes only,
retaining full-blob provenance and span provenance in emitted evidence.

No custom Faust parser is introduced. The existing regex rights-metadata helper
cannot certify complete bodies. Review must establish boundaries and dependency
safety; checksums verify unchanged selections, not semantic validity or reviewer
identity. No production range manifest is approved by this implementation.

## Consequences

Function snapshots without verified ranges now fail closed instead of emitting
whole libraries under function names. Whole-file snapshots remain compatible.
Same-blob non-cleared quarantine and whole rejected-source comparisons remain
unchanged; span review cannot grant rights or bypass those rules. The manifest
has a new schema; Example/unit metadata records the selected range, and the
DedupManifest records its pin even when all functions are sealed or excluded.

H2/H3/FLOOR, function-corpus qualification and signed T07 split freezing remain
separate work. TOKEN_FLOOR is still 40/provisional. This ADR does not accept
ADR-0001 or close any training gate.

See [function spans](../runbooks/function-spans.md) for invocation and tests.
