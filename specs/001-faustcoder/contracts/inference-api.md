# Contract: local inference API (R-010)

Status: DRAFT. Operations are OBSERVED from R-010; request and response shapes
are INFERRED and settle in task T13.

| Operation | Purpose | Journey | Response must include |
|---|---|---|---|
| `generate` | Produce Faust source from a description | J-01 | source, CompilerReceipt, DSPTestReceipt, disposition |
| `repair` | Fix failing Faust within the repair bound | J-02 | diff, receipts for every attempt, disposition |
| `explain` | Explain a Faust program | — | explanation; no correctness claim without receipts |
| `optimize` | Propose a faster equivalent program | J-03 | baseline and candidate measurements, comparison, disposition |

Rules:

- Every response is structured (R-010) and carries a `disposition` from the
  candidate machine (spec §7.2): `accepted`, `rejected` or `abstained`.
- `repair` never exceeds `max_repair_attempts` (R-012).
- `optimize` returns `rejected` when equivalence is unproven (J-03).
- Generated code is compiled and tested only inside the sandbox (R-013).
