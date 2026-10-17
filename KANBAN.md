# FaustCoder implementation backlog

All tasks are **TODO**. Dependency arrows are mandatory promotion gates.

| ID | Milestone | Task | Depends on | Acceptance evidence |
|---|---|---|---|---|
| T01 | v0.1 | Constitution and ADRs | none | Reviewed architectural decisions |
| T02 | v0.1 | JSON schemas and immutable artifact store | T01 | Schema validation and digest tests |
| T03 | v0.1 | Sandboxed Faust compiler harness | T02 | Reproducible compiler receipts |
| T04 | v0.1 | DSP signal test harness | T03 | Known-good/known-bad fixtures |
| T05 | v0.1 | Source rights inventory | T01 | Provenance and exclusion receipts |
| T06 | v0.2 | Normalization and dedup | T05,T02 | Deterministic snapshot |
| T07 | v0.2 | Split freeze | T06 | Leakage checks and signed split manifest |
| T08 | v0.2 | Baseline models | T04,T07 | Frozen baseline measurements |
| T09 | v0.2 | DGX Spark feasibility study | T01 | ARM64/Blackwell throughput and memory receipts |
| T10 | v0.2 | LoRA training | T08,T09 | Pinned reproducible training run |
| T11 | v0.3 | Independent DSP evaluation | T10,T04 | Paired metrics and regression results |
| T12 | v0.3 | Promotion decision | T11 | Human review and decision record |
| T13 | v0.4 | Local serving API | T12 | Contract tests |
| T14 | v0.4 | IDE integration | T13 | End-to-end journey tests |
| T15 | v1.0 | Security and quality review | T14 | Independent audit |
| T16 | v1.0 | Release | T15 | Signed release manifest and rollback test |
