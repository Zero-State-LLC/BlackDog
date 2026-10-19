# ADR-0006: Grade source-attributable compiler failures

Status: ACCEPTED (2026-10-17, Danny)

Accepted 2026-10-17 by Danny. ADR-0006 is in force in reward code.
`grade_receipt` implements A1–A7 (spec §23). Stored compiler classes
stay the ADR-0005 enum.

- Date: 2026-10-17
- Related: [ADR-0005](0005-compiler-diagnostic-classes.md), [compiler runbook](../runbooks/compiler-harness.md)

## Context

ADR-0005 keeps exit 124 (`timeout`), 125 (`resource_limit`) and 126
(`internal`) off the R-005 ladder so a policy cannot farm them. Dropping
those samples has the other effect. A failure the source caused becomes a
way out of the parse-error penalty.

The harness already produces those exits for sources:

- a remote `import`, `library` or `component` is exit 126 `internal`
- deep recursion that overflows the V8 stack is exit 126 `internal`
- a source that runs until the wall clock or the resident cap is exit 124
  or 125

A comment that mentions `https://` hits the same pre-filter. That false
positive is benign only while the exit is not a refuge from a penalty.

An infrastructure fault is a different event: the worker crashes, or
returns `internal`, on a source that compiles when the harness is healthy.
That rate is a property of the harness and the policy's traffic, not of
one DSP program.

## Decision

- **A1:** A failure the source caused gets the `parse_error` rung, the lowest graded rung. That covers: a remote import, library or component; recursion or any other stack overflow caused by the source; a timeout or resource kill the source ran into; any `CompilerExclusion` matched by model output; and any non-finite (NaN/Inf), silent, DC or trivial render in a reward-graded run. A timeout or resource kill counts as source-attributable only once triage attributes it to the source.
- **A2:** The grader never penalizes the model for an error attributable to the evaluation environment or the harness. It distinguishes two such cases, and both are ungraded and quarantined for fixing:
  - (a) a **reproducible infrastructure failure**, i.e. a worker crash or an `internal` receipt reproduced on a known-good fixture under the same harness and environment digest within the same batch;
  - (b) a **deterministic harness defect**, i.e. the harness or environment, not the source, deterministically produces the error for a given input (for example a pre-filter false positive or a crash in harness code), as established by triage.
  Any receipt whose cause has not been attributed yet (an `internal` receipt, a timeout or resource kill with exit 124/125/126, or a worker or harness crash) is ungraded and quarantined until triage attributes it. It is graded under A1 only once it is attributed to the source.
- **A3:** Reward-graded runs force `reject_nonfinite=True`.
- **A4:** The signal comparison covers the whole render up to a pinned `max_frames`. It includes sign and timing beyond `head_frames`, not magnitude alone. `max_frames` and `head_frames` are part of the reward profile digest.
- **A5:** A grader accepts a receipt only when it carries `thresholds.reward_graded` and the canonical profile digest. `apply_signal` takes the receipt.
- **A6:** The remote-import pre-filter matches only the string arguments of `import`/`library`/`component`, not comments. This must land before A1, so that a URL in a comment is not penalised.
- **A7:** Track the ungraded rate per policy (including quarantined A2 samples). Alert when it goes above 1% of samples over a 500-sample window, or above 2× the harness baseline on known-good fixtures, whichever comes first. **PROVISIONAL: the 1%, 500-sample and 2× numbers are provisional starting values, to be tuned after the first runs.**

## Consequences

- A policy cannot dodge a parse error by importing a URL, recursing,
  or allocating until the harness kills the compile. Auto-attribution
  is what turns an unattributed timeout or resource kill into that rung.
- Infrastructure faults stay out of the ladder, and a rising ungraded
  rate is visible instead of being dropped quietly.
- Reward consumers use `grade_receipt` (spec §23). The compiler
  runbook's stored class table is still the ADR-0005 enum.
- A2 quarantine entries are tracked as harness or environment bugs to
  fix.
- A4/A5 specify the fix for ADVERSARY PR41 T04 r3 B1/B2/N4, and
  `grade_receipt` enforces them. A3 closes r2 N1, and A1
  (CompilerExclusion) matches the PR40 T03b note.

## Alternatives considered

- Keep every exit at or above 124 ungraded. Rejected as the proposal:
  source-caused timeouts and remote imports are then a refuge. That
  table was the stored-class behavior until this grader landed.
- Grade every `internal` and `resource_limit` as a model error. Rejected:
  a broken worker on a known-good fixture would punish the policy for the
  harness.

## Amendment 2026-10-17 7:40 PM PT (Q1, Q2)

Jev output sha256 `d9a4632ed29786182ee61e67b7c3a6b1df92c8468f011b8e1331b54e794264df`, run 2026-10-17 7:40 PM PT, authorized by Danny's instruction "use jev to make decisions" (2026-10-17 7:37 PM PT). Record: [jev-output-2026-10-17.txt](../decisions/jev-output-2026-10-17.txt). The fenced blocks are the ruling, copied verbatim from that file. A paraphrase of them is non-normative. The application sentences restate gates from those blocks and do not loosen them. If an application sentence and a fenced block ever diverge, the fenced block wins. This record does not change code.

Q3 and Q4, including acceptance of ADR-0002, are the amendment to
[ADR-0002](0002-training-path.md). The Decision section above is unchanged.
The header of this file is unchanged apart from this amendment being appended.

### Q1 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "P3 reward is binary: 1.0 on full pass, 0.0 on every graded failure including A1's lowest rung. Ungraded samples get no value. Any GRPO group containing a quarantined member is dropped whole from the gradient update, not masked. Its rows are held only for triage and receipts and never re-enter training later. Group-drop rate is tracked per prompt and overall with a halt threshold. The R-005 ladder is a logged diagnostic only, and R-005's wording is amended to say so. A graded reward may enter only via the pre-registered binary-vs-ladder ablation."
```

```text
CONDITIONS:
- C1 is preserved: no ungraded or quarantined row ever contributes a reward value or an advantage, including through group normalization.
- Log group-drop rate per checkpoint and per prompt. If the overall rate exceeds an agreed limit, pause P3 for triage instead of resampling indefinitely. Any prompt dropped repeatedly goes to human triage.
- Log the zero-variance (all-0 or all-1) group rate after SFT. The ε two-level variant is tested only through the ablation, and only if that rate approaches the brief's ~70% trigger.
- Pre-register the ablation's margin, seeds and dev metric before P3 starts. Treat any rise in quarantine or ungraded rate under the ladder arm as a failure of that arm.
- Amend R-005 in the same change set that records this ruling. This also clears ADR-0002 B1, together with Q4.
```

### Q1 application

Q1 CONDITIONS in the fenced block are binding. That includes C1 through group normalization; group-drop logged per checkpoint and per prompt; a halt that pauses P3 for triage instead of resampling indefinitely; human triage for a prompt dropped repeatedly; rows of a dropped group held only for triage and receipts; the zero-variance (all-0 or all-1) group rate logged after SFT; the ε two-level variant only through the ablation, and only if that rate approaches the brief's ~70% trigger; the ablation's margin, seeds and dev metric pre-registered before P3 starts; and any rise in quarantine or ungraded rate under the ladder arm as a failure of that arm.

OBSERVED: `reward_value` in `faustcoder/reward/grader.py` already returns 1.0 for a graded pass, 0.0 for a graded failure including an A1 source failure, and no value for an ungraded sample. This record does not change that function.

### Q2 Jev ruling (verbatim)

```text
DECISION: MODIFIED: "Auto-attribution under A2 is allowed only as A2-T, and only after a shadow period. A2-T requires all of the following:
- ≥2 reruns on a quiet worker reproducing the same crash signature;
- both the trivial and a path-matched known-good fixture passing;
- for stack, wasm_trap, timeout and other harness-limit signatures, a matching native Faust 2.88.0 failure (source-class list alone suffices only for inherently source-side signatures: line-start Faust ERROR, >1 MiB source, remote import);
- the signature not frozen by A7-S.

Every auto-attribution is stored with resolved_by=auto and its evidence. Anything else stays ungraded and quarantined."
```

```text
CONDITIONS:
- Shadow mode first: A2-T computes and logs attributions, but humans triage until A2-T agrees with them on an agreed sample and the gold canary is clean.
- If shadow data shows crash rows below ~0.1% of samples, keep auto-attribution off entirely, following the brief's own fallback.
- If native cross-check is unavailable in the loop, harness-limit signatures stay ungraded. The source-class-only fallback is narrowed to the inherently source-side signatures.
- Exit 124 is attributed only with a native or independent-runner timeout at the same limit, not on fixture evidence alone.
- Gold canary (dev-suite references, cleared-corpus sample, SFT targets) runs on a schedule. Any crash there freezes its signature.
- Land the r5 L1 fix (RangeError restricted to stack overflow), the L2 fix (line-start matching on the failing stage) and the L3 fix (rerun hooks for 124 and 125) before A2-T leaves shadow.
- A7-S thresholds (20% share, 2× rise, 500-sample window) are provisional. They are reviewed against shadow data before going live.
```

### Q2 application

Until A2-T leaves shadow mode, no receipt is auto-attributed to the source. The §23 rerun-plus-trivial-fixture path is not sanctioned by Q2 and must not be supplied (`rerun`/`known_good`) by any training caller. A `runtime_stack_overflow` flag or `wasm_trap` kind attributes to the source only with a matching native Faust 2.88.0 failure. Until then those rows are ungraded and quarantined. The source-class list alone suffices only for a line-start Faust `ERROR` other than `ERROR : stack overflow` (plain or `in eval`; see EVAL-SO), a source over 1 MiB, and a remote import. Shadow mode runs on a separate path that never grades: it may rerun and log attributions, but its output never reaches `reward_value` or a receipt. That path is not a training caller, so needing reruns in shadow does not conflict with A2-PATH. Code follow-up: A2-PATH.

A2-T requires all of: (1) at least 2 reruns on a quiet worker with matching environment digests reproducing the same crash signature; (2) both the trivial known-good fixture and a path-matched known-good fixture (same stage and limit) passing in that environment; (3) for stack, wasm_trap, timeout and every other harness-limit signature, a matching native Faust 2.88.0 failure. If that cross-check is unavailable, the row stays ungraded. (4) The signature is not frozen by A7-S. Exit 124 is attributed only with a native or independent-runner timeout at the same limit, never on fixture evidence alone. Anything else stays ungraded and quarantined.

A2-T leaves shadow only when all hold: L1–L3 have landed; A2-T agrees with human triage on a sample size and agreement level fixed before shadow starts; the scheduled gold canary (dev-suite references, cleared-corpus sample, SFT targets) is clean, and any crash there freezes its signature; the A7-S thresholds have been reviewed against shadow data; and Danny (or the delegated decision process) records the go-live. If shadow data shows crash rows below about 0.1% of samples, auto-attribution stays off entirely. That rate is a reason to stay off, never a reason to go live.

L3. Rerun hooks for exits 124 and 125 on the compile and render stages (r5 L3), feeding A2-T in shadow only.

L1 and L2 have landed in #49 (`f0fcdf9`), on main that also includes #46 (`42ee1e4`). L1 is the r5 fix Jev cited: a RangeError counts as stack overflow only when its message is exactly `Maximum call stack size exceeded`. L2 is the r5 fix Jev cited as line-start matching on the failing stage: `_compile_stack_line` splits on `\n` only. L3 has not landed.

A7-S thresholds (20% share, 2× rise, 500-sample window) are provisional. They are reviewed against shadow data before going live. These numbers are not A7's 1%, 500-sample and 2× ungraded-rate alarm.

After #46, the compiler stores a line that is exactly `ERROR : stack overflow in eval` as exit 126 `internal`. Before #51, the grader's `_COMPILE_STACK_LINES` tagged that line as source with no native check. EVAL-SO's acceptance is the A2-PATH requirement: the grader no longer tags either line as source without the Faust 2.88.0 native match. That covers `ERROR : stack overflow in eval` and the plain line-start `ERROR : stack overflow`. #51 (`cef8a14`) implements this in the grader. A stack line on exit 126 is a source failure only with a sealed `mint_native_stack_match` (faust-cli 2.88.0, `cpp`, exit exactly 1, identical stack line, same source hash). Status: done in code; the production reward path does not yet supply the native receipt.

## Amendment 2026-10-18 (D3 option H)

Danny ruled for option H of the receipts-versus-regrade review. This supersedes any earlier D3 note. The Decision section above is unchanged. A2 is unchanged: an unattributed exit 124, 125 or 126, a worker or harness crash, and an internal error stay ungraded and quarantined. They are not scored 0. A `ShadowLog` is never graded.

What landed with D3-H1, and what did not:

- The library provides a signed group header and one MAC'd reward-row record per member, plus the append-only store. T10 wires that writer into a rollout. No production caller signs, stores, or loads the root key yet. `load_root_key` defaults to `/etc/faustcoder/reward-root.key`. The tag is HMAC-SHA256 under a key scoped to one run. The per-run key is HKDF-SHA256 of a per-Spark root key. That file is mode `0400` and owned by `fc-grader`. The library does not generate, print or log key bytes. A keyring does not derive a key from a run id a row claims.
- Every load re-checks the MAC, the pins, the source hash, the full task digest, the reference and the profile, then `grade_receipt` with no `rerun`, `known_good` or `triage`. `passed` is true only when `metrics.failures` is empty.
- A group with a missing, duplicate, ungraded or quarantined member is dropped whole and claimed in the consumed log. Holds created by the record re-check carry the row id and the group id. Holds created by live `grade_receipt` in the signal harness do not, until T10 writes records. The quarantine index includes resolved holds that carry those ids, so a later file in the same quarantine queue, after the group was first re-checked, that presents that group id as a clean G-1 is still dropped. A stale pin is dropped and is not regraded into training. An A1 source failure stays a graded `0.0` member.
- The sampled rerun-from-source audit (D3-H2) is specified in spec §26, subsection 0.3.9, and is required before P3. Ed25519 is not this amendment. D3-H1 blocks T10. The P3 exit gate adds: audit disagreements = 0 unresolved, and the consumed log intact. The audit is on main: #57 (`63aac31`), halt marker #59 (`ac0326f`), anchor re-verify #60 (`24170c3`), claim pin #61 (`2f1caba`), triage identity #63 (`75d2bed`), name and time bounds #67 (`665d73b`).

## Amendment 2026-10-18 5:11 PM PT (D3-H2 human triage credential)

Danny approved the §26 option C amendment with ADVERSARY's defaults. Exact words: "approved the BlackDog §26 option C spec amendment with ADVERSARY's defaults". Record: [danny-d3h2-option-c-2026-10-18.md](../decisions/danny-d3h2-option-c-2026-10-18.md). Issue #64. The Decision section above is unchanged. A2 is unchanged.

Human triage of a D3-H2 halt is specified in spec §26, subsection 0.3.10. A run-key MAC alone does not clear a halt. Ed25519 in OpenSSH form, verified with `ssh-keygen -Y verify` against `/etc/faustcoder/triage-allowed-signers`, is ruled for that credential only. Ed25519 and DSSE for reward rows and reports remain not ruled. One reviewer clears a disagreement. A halt reported `late` requires two distinct principals. Software keys are allowed, hardware-backed keys are recommended, and Danny's own key must be hardware-backed. Revocation is by `valid-before`. `triaged_at` is not before the halt's persist time and not later than verification time plus 5 minutes. The grader writes `appended_at`, and the key must be valid at that time as well as at `triaged_at`. A later read uses the recorded `appended_at`. OpenSSH 8.7 or newer supplies `-Overify-time` and allowed-signers validity intervals. Pre-signing is not allowed. The option-B checks stay. The recorded writer is the owner of the submitted drop file, not the `fc-grader` process that appends. A missing list, an unknown key, a bad signature, or a parse error leaves the halt in place.

P3 refuses to start or resume unless the grader process runs as its own dedicated `fc-grader` OS account, distinct from any reviewer and from the box user (uid 1000). Signature verification is not implemented by this amendment.

Later ruling, not applied to spec §26 in this text: Danny, 2026-10-18 5:45 PM PT, on issue #68, a software key is fine for his triage key. The D3-H2-C implementation removes the hardware-key requirement for that key and does not enforce a hardware key. The 5:11 PM sentence above still records the approval as merged.
