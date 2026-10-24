# ADR-0010: Exact-tokenizer candidate preflight

Status: Proposed implementation under QR-10; no admission policy change.

## Decision

Use the existing approved Qwen tokenizer assets for a CPU-only preflight of
public instruction candidates. Pin their exact hashes and model revision in the
adapter. Parse the tokenizer JSON directly with the optional tokenizer runtime;
never resolve a remote model, execute model code or load weights. Read asset
bytes through the bounded no-follow reader before constructing the backend.

The original public-pair descriptor remains immutable. A second strict descriptor
references it and the tokenizer files. Readiness replays both, then calls the
canonical completion-only encoder. Reports contain token counts and encoding
hashes only. A successful preflight removes only the tokenizer subcheck from
that candidate report; it clears no dataset, split or training gate.

## Consequences

The portable receipt validator still works without the optional runtime. A
missing runtime leaves preflight unverified. New tokenizer/model revisions need
a separate supported pin, rather than silently accepting a bundle's new claims.
Sequence-bound failures are reported per candidate, without truncation or export
of a partial training batch. Original pending qualifications remain visible.
