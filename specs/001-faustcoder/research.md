# Research: FaustCoder (spec 001)

Phase 0 research for [plan.md](plan.md). This file records each open decision
from spec §14, what is known, and what evidence settles it. Nothing here is a
decision until a DecisionRecord or ADR says so.

| ID | Question | Status | Evidence needed | Settled by task |
|---|---|---|---|---|
| D-001 | Is the target language Faust (Functional Audio Stream)? | Assumed (OBSERVED §14) | Owner confirmation | T01 |
| D-002 | Which student model? | Open | Baseline quality on the frozen suite plus Spark throughput (R-007) | T08, T09 |
| D-003 | Initial sample rates and DSP target runtimes | Open | Task-suite needs; harness cost | T04 |
| D-004 | Corpus redistribution versus training-only rights | Open | Per-source license review | T05 |
| D-005 | Quality gates | Open | Observed baseline and task severity | T08, T12 |
| D-006 | Local-only versus hosted teacher, and data boundaries | Open | Rights and privacy review | T05 |

## Known constraints

- LoRA first; QLoRA only after compatibility and throughput are verified (R-008).
- ARM64/Blackwell compatibility must be verified on DGX Spark before any
  training stack is pinned (§10).
- The V0.2 target of >=90% compile@1 is provisional (§9).
