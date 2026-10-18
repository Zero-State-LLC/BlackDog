# FLOOR open question (b): should a copy that only a lower floor detects count against the higher floors?

**Status:** Ruled. Danny, 2026-10-18 2:27 AM PT, "continue as recommended". The proposed spec text in section 5, with the placeholders filled, is the ruling in [spec §25](../../specs/001-faustcoder/spec.md#lower-floor-detections-038) (0.3.8), [ADR-0002](../adr/0002-training-path.md) and [danny-floor-bounds-2026-10-18.md](danny-floor-bounds-2026-10-18.md). It interprets D6 and does not change the ratified bounds.

- **Asked by:** Danny (owner), "research and recommend". The recommendation below becomes his ruling once it is recorded.
- **Date:** Sunday 2026-10-18, about 2:30 AM PT.
- **Inputs:**
  - BlackDog main `c77a4105` (PR #54 merged), read from a read-only clone in `/tmp`: spec §25, ADR-0002 Q3, tasks.md FLOOR, `docs/decisions/danny-floor-bounds-2026-10-18.md`, `faustcoder/floor_protocol.py`, `docs/analysis/t06-short-kernel-floor.md`.
  - `FLOOR-ruling-2026-10-18.md`, `FLOOR-evaluation-2026-10-18.md`, `FLOOR-impl-brief-2026-10-18.md`, `ADVERSARY-PR54-r1.md`/`-r2.md`, `JEV-decisions-2026-10-18.md`.
  - `floor-labels-2026-10-18/` (`labels.json`, `plant_precheck.json`, `h1_union_precheck.json`). Read only. Nothing from it is quoted here.
- **Mode:** nothing was pushed or commented. The ratified bounds are not changed. No source snippets are quoted. **Spend: $0** (no model calls).
- **Labels:** OBSERVED = computed on the box. INFERRED = reasoned from code, text or numbers. SPECULATIVE = a guess. NOT_COMPUTABLE = the input does not exist yet.

## Recommendation (one line)

**Yes, it counts against the higher floors, with one change from plain A.** Ground truth is fixed before scoring and does not depend on the floor. Planted items stay in their Wilson cells at every floor. A confirmed natural copy (or one still unresolved) that a floor leaves in cleared fails that floor's **item 4 zero-copies count**. It is not added to the planted Wilson cells. (This is option C1: A's definition of truth, scored through item 4.)

## 1. How ground truth is defined today

There are two populations, and they are defined differently.

| Population | Where it is used | Is a positive defined independently of the floor? | Evidence |
|---|---|---|---|
| **Planted items** (8 cells × n = 100) | Item 1, the Wilson recall gate, and item 2 | **Yes.** A positive is a real reject-class span window planted in a cleared host. It is built before any detector runs, and the same set is scored at 40, 30 and 20. | Spec §25 items 1-2 (OBSERVED, text). In `plant_precheck.json` the same 146 spans × 2 hosts are scored at all three floors (OBSERVED). |
| **Natural copies** in the real cleared corpus | Item 3 (FPs) and item 4(a) (zero copies) | **No, as things stand.** (1) The candidate pool is detector output: "added vs floor 40" at floors 30 and 20. (2) Rule R1 itself depends on the floor. It requires a shared run of **at least F tokens**, so the same blob can be a COPY at F = 20 and not a candidate at all at 30 or 40. | `labels.json` rules R1-R4 and `labels.md` (OBSERVED, text). SClarinet is R1 COPY at F = 20 and `in_floor30_survivors: false` (OBSERVED). |

So item 1 is already floor-independent. Option A is simply the literal reading for planted items. The open question only matters for **natural copies**, where nothing in the record currently says that "copy" means something independent of the floor.

**The case that triggers the question (OBSERVED from labels):** `SClarinet.dsp` (cleared) shares a 21-token verbatim CODE run with `NLFfm.dsp`. `NLFfm.dsp` is a whole-file `needs_human` unit, which counts as reject-class under Boof's rights ruling. Only floor 20 detects it. Under the evaluation's literal reading of item 4(a) ("detected ... at the chosen floor"), it does not count against floors 40 or 30 (FLOOR-evaluation:69). Two other items are also only visible below 40. They are unresolved, and the same question applies to them:

- `modulations.dsp`: a 26-token wiring run against `instrReverb`. It is UNDECIDED and only floor 20 flags it.
- `bow` vs `bowTable`: an H1 union-coverage hit of 0.529 at floors 30 and 20. At 40 it is ineligible because `bow` is 38 tokens.

## 2. Standard practice (sources actually fetched)

- **Recall is measured against a fixed gold set.** Manning, Raghavan and Schütze, *Introduction to Information Retrieval*, §8.1 and §8.3. Evaluation needs "a set of relevance judgments", called "the gold standard or ground truth". Recall is "the fraction of relevant documents that are retrieved", and the denominator is the relevant set, not the system's output. Fetched: [IR book §8.1](https://nlp.stanford.edu/IR-book/html/htmledition/information-retrieval-system-evaluation-1.html) and [IR book §8.3](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-unranked-retrieval-sets-1.html)
- **Pooling is the standard way to get judgments when the collection cannot be judged exhaustively.** Relevance is judged over the union of what several systems return (§8.5). The judgments are then used as one shared gold set for every system. Each system does not get its own set. TREC judgments exist "only for the documents that were among the top returned for some system" (§8.2). Fetched: [IR book §8.5](https://nlp.stanford.edu/IR-book/html/htmledition/assessing-relevance-1.html) and [IR book §8.2](https://nlp.stanford.edu/IR-book/html/htmledition/standard-test-collections-1.html)
- **Gold sets built from detector output are biased in code-clone evaluation specifically.** Svajlenko and Roy (ICSME 2015) say of Bellon's benchmark, which was built by validating tool output: "the benchmark is biased and limited by their detection characteristics. The clones these tools were unable to detect form a gap in the benchmark… The tools used to construct the benchmark have an advantage because their clones are in the benchmark." They recommend combining a synthetic (mutation/injection) benchmark with a real-world one. Fetched: [Svajlenko and Roy, ICSME 2015](https://clones.usask.ca/pubfiles/articles/SvajlenkoEvaluatingToolsICSME2015.pdf)
- **The same book warns against tuning on the test set** (§8.1): tuning parameters "to maximize performance on that collection… overstates the expected performance". Choosing TOKEN_FLOOR is parameter selection, so the gold set must not move with the parameter.

What this means for FLOOR (INFERRED):

- The planted cells are the synthetic benchmark. The adjudicated natural copies are the pooled real-world benchmark.
- Both must be a single gold set shared by all floors.
- A natural set pooled from floor-20 output favours floor 20 by construction. It should therefore gate only where the bias does not matter: a zero-tolerance count of real copies. It should not be pooled into a recall estimate.

## 3. The options

### A: yes, count it as a recall miss at higher floors (plain form: add it to the Wilson cell)

- **Zero-copies rule:** it does not directly strengthen item 4. Adding a natural copy to the 20-29 verbatim cell at 40 only uses up 1 of the 4 tolerated misses. So a real reject-class copy left in cleared could be *tolerated* by the recall gate. That conflicts with the spirit of the zero rule (INFERRED).
- **Circularity / Goodhart:** the truth definition is not circular. The pool is still detector-sourced, and adding pool items to cells mixes a detector-selected sample into a designed sample, which is the Bellon-style bias above (INFERRED).
- **Picking the highest passing floor:** correct direction. A higher floor cannot gain from being blind.
- **Wilson cells:** it breaks the design.
  - Item 2 fixes n = 100 planted items from at least 50 windows × 2 hosts. Natural items would make n = 100 + k.
  - "At most 4 misses" is computed for n = 100. `max_misses(101)` is also 4 (OBSERVED), but the cell would no longer be the sample that was ratified.
  - Item 2 also doesn't say whether a natural miss is a "miss with a recurring mechanism". ADVERSARY r1 noted this ambiguity (B1/N2).

### B: no, it counts only at floors where it is detectable

There are two ways to read it, and both fail.

- **B-planted** (drop items shorter than F from F's cells). Every planted span below F leaves the denominator, so each floor is graded only on what it can see. On the precheck data (OBSERVED, `plant_precheck.json`, R = span, raw verbatim; not the gated run):
  - floor 40 keeps only the 40+ cell, 180/180, Wilson lower bound 0.9791, so it **passes** recall;
  - meanwhile it detects 0 of the 112 short-bucket planted items.
  - Floors 30 and 20 then fail only because their 30-39 cell has n = 30 < 35 (lower bound 0.8865).
  - "Highest passing" would then pick 40. This is pure circularity: every floor scores 100% on what it can detect.
- **B-natural** (the evaluation's literal reading of item 4(a)). A natural copy counts only at floors that detect it.
  - **Zero-copies rule:** hollowed out at higher floors. SClarinet stays in cleared, and 40 and 30 still report "0 left unquarantined". The rule becomes "zero copies *that this floor can see*" (INFERRED).
  - **Goodhart, interaction with highest passing:** under B, a lower floor's extra sensitivity counts against it. The H1 check shows this concretely:
    - floors 30 and 20 carry an unresolved H1 hit (`bow`, 0.529);
    - floor 40 reports 0 hits only because `bow` is too short to be eligible (OBSERVED, `h1_union_precheck.json`: 0 / 2 / 2 raw-stream hits at 40 / 30 / 20, one of which is the `mixer.dsp` header that disappears after declare-stripping).
    - Item 3 (FP budget) already penalises lower floors. B adds a second penalty for the same sensitivity. Combined with "pick the highest", the protocol then systematically rewards the blindest floor (INFERRED).
  - **Wilson cells:** unaffected, because naturals aren't in cells. But natural recall is 100% by definition at every floor, so nothing is learned.

### C1 (recommended): A's truth definition, scored through item 4, cells planted-only

1. **One floor-independent gold set.**
   - **Planted items** are positives at every floor. No item leaves a cell because it is shorter than F.
   - **Natural candidates** are pooled from everything any FLOOR-run check flags: floors 40, 30 and 20, sub-15 exact hash, and H1. Each candidate is adjudicated **once, on content**, as COPY or NOT_COPY of reject-class text. Reject-class means `rights_rejected`, or `needs_human` until cleared (Boof's ruling).
   - The adjudication uses a fixed minimum of 15 tokens, the smallest gated bucket, not R1's floor-dependent F. It is frozen before any floor is scored.
2. **Item 4(a) counts every adjudicated COPY, and every candidate still unadjudicated, that floor F's shipping pipeline leaves in cleared.**
   - Item 4 says "At the chosen floor, three counts must be zero: detected reject-class matches left unquarantined". That text does not say "detected *by the chosen floor*". So this reading uses the ratified words without changing them (INFERRED). It is still a stricter reading than FLOOR-evaluation:69, which is why it needs Danny's ruling.
   - Unresolved counts as failing, by analogy with item 4(b) ("unresolved sub-15 ... hits") and Boof's fail-closed rights ruling.
3. **Only F's own pipeline counts.** Manual quarantine pins are applied for hygiene but are not credited to F. Otherwise 40 could "pass" by pinning what a one-off floor-20 run found, and the blind spot would come back on the next corpus refresh.
4. **Cells stay planted-only, n = 100.** Natural misses are inspected and their mechanism is recorded, like planted misses. Per-floor natural recall (detected / adjudicated COPY) is **reported, not gated**, with the pool-bias caveat.

How C1 fares on the four criteria:

- **Zero-copies rule:** fully enforced. A real copy in cleared fails any floor that leaves it there.
- **Circularity / Goodhart:** the definition of truth does not depend on the floor. The pool's detector bias only enters a zero-tolerance count, where the only possible effect is fail-closed.
  - Residual Goodhart risk: an adjudicator could call a borderline copy NOT_COPY to rescue a higher floor. The mitigation is to adjudicate before scoring, and to require a second reviewer for any item whose label decides the floor.
- **Highest passing floor:** detection is nested across floors (INFERRED from `neardup.py:239`, `:459-467`: a run of at least 40 contains one of at least 20, and reverse-containment eligibility is monotone in F). It is also consistent with the floor-30 survivors being a subset of the floor-20 survivors (OBSERVED, labels.md). So with a fixed gold set, item 4 can never favour a higher floor over a lower one.
  - Items 1 and 4 push down, item 3 pushes up, and "highest passing" picks the tightest trade-off. That is the intended design.
- **Wilson cells:** untouched. n = 100, at most 4 misses, z = 1.96, no continuity correction.

### Other hybrids considered and rejected

- **C2: add naturals to the cell (n = 100 + k).** This is plain A. It breaks the ratified sample design and lets a real copy hide inside the 4 tolerated misses.
- **C3: report under A, select under B.** Selection is where Goodhart bites. This keeps the circularity in the decision itself.
- **C4: treat every natural miss as a "mechanism miss" under item 2.** It gets the same blocking result as C1, but item 2 is written for planted misses, and ADVERSARY flagged that ambiguity (B1/N2). Item 4 is the clean home for real-corpus copies.

## 4. Impact on today's pass/fail

Caveats:

- The gated run is **NOT_COMPUTABLE**: no H2/H3, no idioms allowlist, no real slicer, no 8 × 100 planted set.
- The recall figures are the **non-gated precheck** (unsliced hosts, raw verbatim only, n ≠ 100), so they are indicative only.
- Rename-canonical cells: NOT_COMPUTABLE under every option.

| Floor | Item 1 recall, A / C1 (planted fixed) | Item 1 recall, B-planted | Item 3 FP (≤ 25) | Item 4(a), B-natural | Item 4(a), A / C1 | Item 4(c) H1, B | Item 4(c), C1 | Overall today |
|---|---|---|---|---|---|---|---|---|
| **40** | FAIL. 15-19: 0/18, 20-29: 0/64, 30-39: 0/30 (lower bound 0.0); 40+: 180/180 (0.9791). OBSERVED | **PASS**. Only 40+ remains, 180/180. OBSERVED | PASS, 0. OBSERVED | 0. INFERRED | **1** (SClarinet, pending human confirmation it is not a shared-author idiom); +1 if `modulations` is adjudicated COPY; counts as failing while unresolved. INFERRED | 0 (bow ineligible, vacuous). OBSERVED raw precheck | Same adjudication as 30/20 applies. If `bow`/`bowTable` is a COPY, 40 also leaves it in cleared, so it fails. INFERRED | **FAIL** under A/C1. Under B-planted plus B-natural, the only blockers left are the NOT_COMPUTABLE checks. |
| **30** | FAIL. 15-19: 0/18, 20-29: 0/64; 30-39: 30/30 (0.8865, n < 35); 40+: 180/180. OBSERVED | FAIL. 30-39 has n = 30 < 35. OBSERVED (would pass at n = 100, INFERRED) | PASS, worst case 14. OBSERVED | 0. INFERRED | **1**, plus `modulations` as at 40. INFERRED | 1 unresolved (`bow`), so FAIL until resolved. OBSERVED raw precheck | Resolved once, the same answer at every floor. INFERRED | **FAIL** under every option. |
| **20** | FAIL. 15-19: 0/18; 20-29: 64/64 (0.9434); 30-39: 30/30 (0.8865); 40+: 180/180. OBSERVED | FAIL. 30-39 has n = 30. OBSERVED | PASS, worst case 25 (zero slack, pre-allowlist). OBSERVED | 0. INFERRED | 0. SClarinet and `modulations` are both flagged at 20, so they are quarantined. INFERRED | 1 unresolved (`bow`). OBSERVED raw precheck | As at 30. | **FAIL** (15-19) under every option. |

**Does the recommendation change which floor currently passes? No.** No floor passes today under the ratified bounds, whichever option is chosen:

- the 15-19 cells fail at every floor on unsliced hosts;
- the gated checks are NOT_COMPUTABLE.

What the choice does change:

- **Against B-planted:** it removes a spurious recall pass at 40 (OBSERVED on the precheck).
- **Against B-natural, going forward (INFERRED):**
  - If SClarinet is confirmed as a copy, floors 40 and 30 fail item 4 on today's corpus **even if the gated recall run later passes**. That holds unless (i) a human rules it a shared-author idiom, or (ii) the shipping pipeline at 40/30 catches it some other way (for example the real slicer plus exact hash, or the item-5 function-unit fallback).
  - Whether (ii) happens is SPECULATIVE. The fallback keeps whole files at 40, and `NLFfm.dsp` is a whole-file unit.
  - So this ruling **can decide the floor**, toward 20 or toward the fallback. The labels show the FP budget at floor 20 has zero slack (worst case 25 of 25, OBSERVED), so a forced move to 20 rests on one adjudication and the not-yet-built allowlist.

## 5. Proposed spec text

Danny ruled this text (2026-10-18 2:27 AM PT, "continue as recommended"). The placeholders are filled in spec §25, ADR-0002 and `docs/decisions/danny-floor-bounds-2026-10-18.md`. The same ruling is on the FLOOR entry in tasks.md, KANBAN and the T06 notes, which closes ADVERSARY r2 N9. The block below is the proposal as it stood before those placeholders were filled.

> Ruling on lower-floor detections (Danny, 2026-10-18 [time] PT, "[exact words]"; record: FLOOR-ruling-b-recommendation-2026-10-18.md). This interprets the ratified D6 bounds and does not change their text or numbers.
>
> 1. Ground truth for the FLOOR run is fixed before scoring and does not depend on TOKEN_FLOOR. The same gold set is used for 40, 30 and 20.
> 2. Planted items: every planted item is a positive at every candidate floor. A planted item that a floor misses is a miss in that floor's cell, whatever its length. No item leaves a cell's denominator because it is shorter than the floor. Cells stay at n = 100 planted items.
> 3. Natural copies: the candidate pool is the union of everything flagged at floors 40, 30 and 20, by the sub-15 exact-hash check, and by the H1 union-coverage check, on the shipping path. Each candidate is adjudicated once, on content, as COPY or NOT_COPY of reject-class text (rights_rejected, or needs_human until cleared), with a 15-token minimum and without regard to which floor flagged it. The adjudicated set is frozen before any floor is scored. Natural copies do not enter the Wilson cells.
> 4. Item 4's first count ("detected reject-class matches left unquarantined in cleared") counts, at floor F, every adjudicated COPY and every unadjudicated candidate that F's own shipping pipeline leaves in cleared. A copy that only a lower floor detects therefore fails item 4 at every higher floor that leaves it in cleared.
> 5. Only quarantines produced by F's shipping pipeline count for F. Manual quarantine pins may be applied for corpus hygiene but do not make F pass.
> 6. Every natural miss is inspected and recorded with its mechanism. Per-floor natural recall (detected / adjudicated COPY) is reported and not gated, and the report states that the pool comes from the detectors themselves.

Optional code mirror (proposed only, matching `NEEDS_HUMAN_REJECT_CLASS`): a `LOWER_FLOOR_DETECTIONS` record in `faustcoder/floor_protocol.py` with `who`, `when`, `record` and `part_of_d6=False`, and a test that asserts the data fields, not docstring prose (ADVERSARY r1 N4).

## 6. Risks

1. **One 21-token line can decide the floor.** If SClarinet is confirmed as a copy, 40 and 30 fail item 4 on today's corpus. The labels already flag it as a possible shared-author idiom, so its adjudication is now decision-critical. Use two reviewers and record both.
2. **Pool bias.** The natural set only contains what some check flagged, mostly floor-20 output. Copies that no check sees are invisible; the planted cells are the guard against that. Natural recall would favour floor 20, which is why it is reported and not gated (Svajlenko and Roy).
3. **Adjudication Goodhart.** Pressure to rule borderline items NOT_COPY to rescue a higher floor. Mitigation: adjudicate before scoring, record which floor flagged each item separately, and require a second reviewer for any floor-deciding item.
4. **Interpretation challenge.** C1 reads item 4(a)'s "detected" as "detected by any FLOOR-run check". That is stricter than the evaluation's literal reading. It is admissible under the ratified wording, but a reviewer could call it a change to the bounds. That is why it needs Danny's recorded ruling and must not be filed as D6 (ADVERSARY r1 B1).
5. **Fail-closed on unresolved items.** `modulations` and `bow`/`bowTable` block floors until a human rules on them. That adds human work before FLOOR can close.
6. **Corpus drift.** The gold set is specific to the corpus. Re-adjudicate on any refresh of the cleared set (N_cleared ≠ 491) or of the rights inventory.
7. **Doesn't fix the 15-19 problem.** On unsliced hosts no floor passes 15-19 under any option. That still needs its own ruling if the real slicer does not fix it (FLOOR-evaluation item 1).
