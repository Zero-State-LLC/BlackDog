# ADR-0011: Saved public signal replay

Status: Proposed implementation under QR-03; no admission policy change.

## Decision

Connect preserved public samples to readiness using a separate strict descriptor.
Replay original pair bindings and exact executed-contract closure hashes before
reading explicit plan, WASM, input, output and mutant-source references. Require
both rates and every sweep/default/mutant case category for each selected unit.
Evaluate only a bounded affine arithmetic grammar over saved float32 data.
Keep the original absolute and relative tolerances and wrong-reference control.

## Consequences

A successful replay establishes numerical consistency of saved samples with
bound formulas. It does not prove the samples came from the referenced WASM or
that the recorded default/probe labels describe authenticated execution. No
archived code runs. Compiler provenance, semantic approval, canonical admission,
signed membership and training authorization remain blocked. Reports disclose
hashes, counts and error magnitudes only. Imported-contract wording is accepted
only in the existing approved correction format, bound to the closure hash.
