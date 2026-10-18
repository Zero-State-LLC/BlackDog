# FLOOR bounds: Danny's ruling (D6 ratified)

- **Who:** Danny (owner, Zero State).
- **When:** Sunday 2026-10-18, 12:34 AM PT.
- **Exact words:** "continue as recommended".
- **Choice:** the 5% FP budget, not 2%.
- **What it ratifies:** the FLOOR acceptance bounds (D6), the "The ask" block of the 2026-10-18 bounds recommendation, with the 5% budget option.
- **What it does not ratify:** a value for the length constant. That value stays 40 and provisional until the FLOOR run applies these bounds ([ADR-0002](../adr/0002-training-path.md) Q3, C2).
- **Recorded in:** [spec §25](../../specs/001-faustcoder/spec.md) and [`faustcoder/floor_protocol.py`](../../faustcoder/floor_protocol.py).

## Status change

D6 (FLOOR bounds) moves from PROVISIONAL to **RATIFIED**. This ruling replaces Jev's D6 numbers wherever they differ:

- n = 100 per cell, not "at least 35";
- the budget scales with the corpus;
- the FP count is of labelled survivors, not the raw 26.

## The ratified bounds (exact)

1. **Recall.** In each of 8 gated cells, the 95% Wilson lower bound on recall must be at least 0.90.
   - The cells are 4 buckets (15-19, 20-29, 30-39 and 40+ tokens) times 2 operators: verbatim on the raw stream, and consistent rename on the canonical stream.
   - Other operators are reported, not gated.
2. **n = 100 planted items per cell.** These come from at least 50 distinct real reject-class span windows, each planted in 2 different cleared hosts in different repos.
   - At most 4 misses per cell. 96/100 gives a Wilson lower bound of 0.9016; 95/100 gives 0.8882.
   - Window-level recall is reported and not gated.
   - The 15-19 bucket is filled with statement-boundary windows cut from longer reject-class spans.
   - Every planted miss is inspected. A miss with a mechanism (one that would recur) blocks until fixed, even if the Wilson bound passes.
3. **FP budget:** B = ceil(0.05 × N_cleared). Today that is ceil(0.05 × 491) = 25.
   - Count only hand-confirmed non-copy blobs (idiom, boilerplate, header, import or numeric table) added beyond the floor-40 set.
   - Count after declare-stripping and the idioms allowlist.
   - If a floor adds 100 or fewer candidates, label all of them. Otherwise label a seeded random sample of at least 50, and require (Wilson 95% upper bound of the FP share) × (added count) to be at most B.
   - The budget does not scale with the floor. Floor 20 is not excluded in advance.
4. **Reject-class rule.** At the chosen floor, all of the following must be zero:
   - detected reject-class matches left unquarantined in cleared;
   - unresolved sub-15 exact-hash hits (ID/NUM stream);
   - H1 split-file union-coverage hits at 1/2 or more.
5. **Choosing the floor.** Choose the highest TOKEN_FLOOR in {40, 30, 20} that passes items 1, 3 and 4. If only the 20-29 and 30-39 cells fail at 40, use the function-unit-only lower floor that tasks.md and Q3 already allow, and whole files keep 40.

> FLOOR acceptance bounds (ratified by Danny 2026-10-18 12:34 AM PT, "continue as recommended", 5% FP budget):
>
> 1. Recall: in each of 8 gated cells, which are 4 buckets (15-19, 20-29, 30-39 and 40+ tokens) times verbatim on the raw stream and consistent rename on the canonical stream, the 95% Wilson lower bound must be at least 0.90. Other operators are reported, not gated.
> 2. n = 100 planted items per cell, from at least 50 distinct real reject-class span windows, each planted in 2 cleared hosts in different repos. That tolerates at most 4 misses per cell. Every planted miss is inspected, and a miss with a recurring mechanism blocks until fixed.
> 3. FP budget B = ceil(0.05 × N_cleared), which is 25 at N_cleared = 491. It counts hand-confirmed non-copy blobs (idiom, boilerplate, header, import, numeric table) added beyond the floor-40 set, after declare-stripping and the idioms allowlist. Label every candidate if a floor adds 100 or fewer. Otherwise use a seeded sample of at least 50 and require Wilson-upper(FP share) × added ≤ B.
> 4. At the chosen floor, three counts must be zero: detected reject-class matches left unquarantined in cleared, unresolved sub-15 exact-hash hits on the ID/NUM stream, and H1 split-file union-coverage hits at 1/2 or more.
> 5. Choose the highest TOKEN_FLOOR in {40, 30, 20} that passes 1, 3 and 4. If only the 20-29 and 30-39 cells fail at 40, use a function-unit-only lower floor, and whole files keep 40.
>
> TOKEN_FLOOR stays 40 and provisional until the FLOOR run applies these bounds.

The figure of at most 4 misses at n = 100 depends on a two-sided Wilson interval with z = 1.96 and no continuity correction.

## Known correction carried with the ruling

The correction was that the 26 floor-20 declare-stripped survivors were **unlabeled survivors, not confirmed FPs.** Jev's D6 sentence that 25 "sits above" both 14 and 26 was wrong for floor 20, and the FP count has to come from labels. Those survivors are now labelled. Summary counts, reading A (COPY / FP / UNDECIDED), are in [t06-short-kernel-floor.md](../analysis/t06-short-kernel-floor.md) (Amendment 2026-10-18). The labels file is not in this repository. It quotes `rights_rejected` and `needs_human` source, which [ADR-0003](../adr/0003-licensing-and-data-rights.md) forbids redistributing.

## Separate rights ruling

Not part of D6, and not Danny's ratified text.

needs_human sources count as reject-class until a human clears them (fail closed). Boof (orchestrator), rights call under Danny's 2026-10-17 BlackDog rights/licensing delegation ([rights-inventory.md](../rights-inventory.md) lines 21-22), 2026-10-18 ~12:57 AM PT.

## Open question for Danny

Not a rule, and not part of the ratified bounds. Danny has not decided whether a hit that shows up only when the floor is lowered is scored as a miss in a higher floor's recall cell. The ratified D6 cells govern until he decides.

## Preconditions unchanged

The run still happens only after H2 (canonical ID/NUM stream, OR'ed with raw) and H3 (NFKC, drop Cf/Cc), plus the idioms allowlist and the real slicer, have landed. ADVERSARY confirms on the shipping slicer path (Q3 verbatim, ADR-0002).
