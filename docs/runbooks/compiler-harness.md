# Runbook: sandboxed Faust compiler

T03 compiles Faust DSP with libfaust from `@grame/faustwasm` 0.19.0. Python
starts that process in a network namespace. The receipt schema is spec
0.3.2 ([ADR-0005](../adr/0005-compiler-diagnostic-classes.md)).

## Reward consumers

Key on the pair `(exit_code, diagnostic_class)`.

| Exit | Class | Graded |
|---|---|---|
| 0 | `ok` or `warning` | yes, top of the R-005 ladder |
| 1 | `parse_error`, `type_error`, `arity_error`, `unbound_symbol`, `other` | yes |
| 124 | `timeout` | no |
| 125 | `resource_limit` | no |
| 126 | `internal` | no |

Exit codes 124 and above are ungraded. They are not rungs on the ladder.
Do not score `internal` or `resource_limit` as `other`. `unbound_symbol`
is a compiler result (exit 1), the class for libfaust `undefined symbol`.

A receipt with exit 124 or above records the same compiler pin as a
successful compile (`faust_version`, `environment_digest`). It is not
evidence that another operator reproduced a successful compile of that
source. Compare `reproducible_digest` only across receipts with the same
exit code and diagnostic class. `reproducible_digest` drops `duration_ms`
and nothing else. Store and look up receipts with that digest;
`artifact_id` still includes `duration_ms`, and a second store of the
same digest returns the first envelope.

## What the environment digest covers

The hashed object includes the embedded libfaust version, the bundled
faustlibraries `vl.version` triplet, the sha256 of `libfaust-wasm.data`,
the sha256 of `libfaust-wasm.js`, `.wasm` and `.data`, and the Node
major.minor. It does not include the host name, the Node patch, or the
job directory.

`stdfaust.lib` and `all.lib` in this bundle do not declare a version.
`version.lib` does. On faustwasm 0.19.0 that triplet is 2.74.2.

The ADR-0004 / T05 pin is faustlibraries commit `2edec0537f53` (2026-10-15),
whose `version.lib` declares 2.80.0, next to native Faust 2.88.0. The wasm
bundle is libfaust 2.90.0 with libraries 2.74.2. Those are not the same
pin. A native cross-check can disagree because the compiler version
differs or because the libraries differ. This harness records the bundle
it actually ran. It does not stage the T05 commit into the Emscripten
filesystem.

## Network namespace on a runner

The compiler runs as `unshare --net --map-current-user`. The uid inside
the namespace is the calling user, not 0, and `CapEff` is 0. A connect
fails with `ENETUNREACH`.

GitHub-hosted Ubuntu sets `kernel.apparmor_restrict_unprivileged_userns=1`.
The pytest job clears that sysctl only when `runner.environment` is
`github-hosted`. The runner is ephemeral.

On a DGX Spark or any self-hosted runner, do not set that sysctl. It is
host-wide and lasts until reboot, and it re-opens unprivileged user
namespaces for every process. Install a per-binary AppArmor profile that
grants `userns` to the node binary used by the harness, and to `unshare`
if the profile must name it. Do not use a profile that grants `userns` to
every binary, and do not write `kernel.apparmor_restrict_unprivileged_userns=0`
on those machines.

Example profile, installed by an operator on the Spark, not by CI:

```text
abi <abi/4.0>,
include <tunables/global>

profile faustcoder-node /usr/bin/node flags=(unconfined) {
  userns,
}
```

The path must be the node binary the harness executes. `flags=(unconfined)`
keeps the rest of the node's confinement unchanged and adds only the
`userns` permission AppArmor requires before `unshare` can write the uid
map. Reload AppArmor after installing the profile. Confirm with
`unshare --net --map-current-user -- true` as the user that will run the
harness, without changing the sysctl.

## Remote imports

A textual `import`, `library` or `component` of an `http://` or `https://`
URL is rejected before the worker starts. The receipt is exit 126,
`internal`, diagnostic `internal: remote import rejected`. The network
namespace is still the control that holds if a later faustwasm build
fetches URLs the filter does not recognize.
