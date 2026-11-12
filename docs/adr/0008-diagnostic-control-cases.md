# ADR-0008: Bounded diagnostic control and input cases

Status: Owner-approved amendment; implementation proposed for review.

## Context and decision

OBSERVED: Before this change, `renderOne` broadcasts the same mono input to all
DSP inputs and applies the first-block button policy. Issue #108 needs bounded
control changes, independent channel stimuli and guarded expected-zero tests.
The owner approved the bounded proposal and implementation on 2026-10-22 PT,
including spec §27 and plan edits, tests and a separate PR. No merge is authorized.

Use immutable case records with sorted events and deterministic per-input buffers.
Validate once against the Python request and again at the compiled worker boundary.
Apply events before compute and persist them. Explicit button schedules require
legacy automatic pressing off. Legacy rendering remains a separate unchanged
function, and extension fields are omitted when unused.

`run_diagnostic_cases` executes all cases itself. It never accepts a caller's
companion receipt. Expected-zero results start failed; the runner removes only
silence/pending failures after a passing non-silent companion with matching
compiler and harness identity. Require full-frame explicit zero references and
retain the pinned comparison tolerances. Reject cycles and zero companions.

## Evidence and consequences

OBSERVED: Tests in `tests/test_diagnostic_cases.py` cover validation, optional
profile binding, frozen reward identities, companion failures and signed full
comparison. `tests/diagnostic_worker_checks.mjs` checks block-zero/last-block
application, persistence, per-input routing and zero-input processing. The Linux
integration test compiles controls, channel routing and an always-zero mutant
through the production sandbox; non-Linux hosts skip that integration test only.

The version-2 profiles remain unchanged without the extension. Enabled profiles
carry diagnostic extension version 1 and cannot enter the reward allowlist.
Receipts bind complete case definitions, applied controls, input hashes, descriptor
hash, diagnostic code and companion receipt. Harness digests change when worker
code changes, as intended; profile digests do not change for legacy calls.

NOT_COMPUTABLE from these tests: general DSP equivalence, corpus qualification,
human review independence or admission. Existing resource/isolation requirements
remain. TOKEN_FLOOR=40 stays provisional, T07 stays unfrozen and both detector
features stay default-off. Host and production admission remain separate gates.
