# ADR-0001: Two distinct graphs

Status: PROPOSED

## Decision

Use an immutable, content-addressed acyclic evidence graph for development lineage. Model Faust DSP as a typed signal-flow graph with explicit state and delay boundaries. Legal recursive Faust compositions are not rejected merely because they contain feedback.

## Consequences

Evidence parent links must not form cycles. Changing an upstream artifact requires new downstream evidence. A compiler check is necessary but insufficient for DSP acceptance. Graph transforms require behavior checks and may not claim equivalence without evidence.
