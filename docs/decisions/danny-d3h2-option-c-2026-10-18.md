# D3-H2 option C: Danny's approval of the human triage credential

- **Who:** Danny (owner, Zero State).
- **When:** Sunday 2026-10-18, 5:11 PM PT.
- **Exact words:** "approved the BlackDog §26 option C spec amendment with ADVERSARY's defaults".
- **What it ratifies:** the D3-H2 human triage credential, as the subsection under spec §26 (0.3.10). Issue #64. It tightens item 7 of the 0.3.9 audit rules. It does not change items 1 to 6 or 8, the H1 text, the HKDF run keys, or ADR-0006 A2.
- **Recorded in:** [spec §26](../../specs/001-faustcoder/spec.md) and [ADR-0006](../adr/0006-source-attributable-failures.md).
- **Source draft:** ADVERSARY, 2026-10-18, grounded at main `75d2bed`. The eight credential rules in §26 are that draft's drop-in text. This record is the approval, including the defaults the draft left open and the P3 account precondition Danny added.

## Approved choices

These are ADVERSARY's recommended defaults, as Danny approved them.

- **Keys.** Each human triager holds an Ed25519 key in OpenSSH format. Software keys (`ssh-ed25519`) are allowed. Hardware-backed keys (`sk-ssh-ed25519@openssh.com`) are recommended. Danny's own key must be hardware-backed.
- **Verification.** `ssh-keygen -Y verify` against `/etc/faustcoder/triage-allowed-signers`, namespace `faustcoder-triage-v1`, with `-Overify-time` taken from `triaged_at` (OpenSSH 8.6 or newer). No new Python dependency.
- **Allowed signers.** The file is owned by root, mode `0644`, in root-owned `/etc/faustcoder`. `fc-grader` cannot write the file or its directory. Revocation is by expiry (`valid-before`). An entry is not deleted while any run that used it is retained.
- **Quorum.** One reviewer clears a disagreement. A halt reported `late` (the group was already claimed `used`) requires 2-of-N: two valid signatures from two distinct principals.
- **Time.** `triaged_at` is never earlier than the halt line's persist time, and not later than verification time plus 5 minutes.
- **Pre-signing.** Not allowed. The statement binds `halt_report_mac`, which does not exist until the halt line is persisted.
- **Option B.** Kept. `triaged_by`, RFC 3339 `triaged_at`, and the writing OS user stay. They are hygiene, not authority. `fc-grader` and root still do not clear a halt.
- **Fail closed.** A missing allowed-signers list, an unknown key, a bad signature, or a parse error leaves the halt in place.
- **Append path (draft D7).** The grader appends human-signed statements submitted through a drop directory the human can write and `fc-grader` can read. The grader cannot forge their content.

## Addition

P3 entry precondition, in addition to the draft's rules. P3 must not start or resume unless the grader process runs as its own dedicated `fc-grader` OS account, distinct from any reviewer and from the box user (uid 1000). P3 refuses to start otherwise.

## Not ruled

Ed25519 and DSSE for reward rows and reports. The audit cadence after P3 starts. Any numeric halt threshold other than zero disagreements. Compromise of a human key, root on the host, snapshot rollback of both logs, and social engineering of a triager stay outside this credential, as the subsection says.
