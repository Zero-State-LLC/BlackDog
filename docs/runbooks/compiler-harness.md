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

[ADR-0006](../adr/0006-source-attributable-failures.md) proposes grading
source-attributable failures (remote import, recursion, a source-caused
timeout or resource kill) at or below `parse_error`, leaving ungraded only
an infrastructure fault, and alerting on the ungraded rate per policy. It
is Proposed and awaiting Danny. It does not change this table.

A receipt with exit 124 or above records the same compiler pin as a
successful compile (`faust_version`, `environment_digest`). It is not
evidence that another operator reproduced a successful compile of that
source. Compare `reproducible_digest` only across receipts with the same
exit code and diagnostic class. `reproducible_digest` drops `duration_ms`
and nothing else. Store and look up receipts with that digest;
`artifact_id` still includes `duration_ms`, and a second store of the
same digest returns the first envelope.

## What the environment digest covers

The hashed object includes the embedded libfaust version, the staged
faustlibraries commit `2edec0537f53`, the sha256 of that canonical checkout,
the sha256 of the tree mounted at `/usr/share/faust`
(`faustlibraries_share_sha256`), the staged `vl.version` (`2.80.0`), the
triplet still embedded in `libfaust-wasm.data` (`2.74.2` on faustwasm
0.19.0), the sha256 of `libfaust-wasm.js`, `.wasm` and `.data`, and the
Node major.minor, and the resolved path and sha256 of the `unshare`
binary that actually runs. `FAUSTCODER_UNSHARE` unset means the system
`unshare`. A swapped wrapper changes `environment_digest` before the
network canary runs. The digest does not include the host name, the Node
patch, the job directory, or the host path of the library tree.

The canonical tree hash is every regular `*.lib` file, sorted by relative
path. Each entry is the UTF-8 path, a newline, an 8-byte big-endian
length, and the file bytes. The checkout hash and the mounted-share hash
differ because the share also contains the flat `old/*.lib` and `dx7/*.lib`
copies. The digest binds the mounted hash. The worker hashes the bytes it
writes into `/usr/share/faust` on every compile and the harness refuses
the result unless that hash is the pin. The host share is hashed again on
every reuse. A `.tree-sha256` stamp is not evidence. One changed byte of
the mounted tree changes `environment_digest`, and a mismatch is refused
before a receipt is written. A checkout that does not match the pinned
hash is refused the same way.

`scripts/fetch-faustlibraries.sh` downloads the commit on the host. The
sandbox does not. Before every wasm compile the worker deletes
`/usr/share/faust` in the Emscripten filesystem and writes that share.
The native 2.88.0 cross-check passes the same directory as `-I`.
The logical command records `--faustlibraries=2edec0537f53`.

The data file still contains libraries 2.74.2. Those bytes are hashed so
the runtime identity stays in the digest. They are not the libraries the
compiler imports. `fa.`, `pt.` and `si.softmax` resolve against the pin.
`ts.fi`, which 2.74.2 exported and the pin does not, is `unbound_symbol`.

Do not run a T06 or T07 compile check, and do not feed a receipt into a
reward, on a harness that skipped this staging.

## Multi-file sources and stack size

`compile_directory` reads the `.dsp` files under one directory and stages
them for `import` and `component`. Relative paths such as
`../dynamic/volume.dsp` resolve when the directory is their common parent.
Ten of the thirteen Faust 2.88.0 multi-file examples then compile. The
other three (`SAM/echo/echo.dsp`, `SAM/effects/echo.dsp`,
`SAM/effects/effects.dsp`) embed `ffunction` `fastpow2` and are recorded
exclusions, not `other`.

Node `--stack-size` is kilobytes of V8 stack. The default overflows on
`physicalModeling/fds/2dKirchhoffThinPlate.dsp`. 6144 KB still overflows.
6272 KB is the smallest size observed to compile it on Node 22. The
harness sets `--stack-size=8192` (8 MiB). That flag is part of
`environment_digest`. Do not raise the stack further without remeasuring
resident memory.

The resident cap is 768 MB. The plate compile stays near 510 MB.
`SAM/virtualAnalog/virtualAnalog.dsp` exceeds 608 MB and compiles at 640
MB, so 512 MB is not enough once its sibling is staged. 768 MB leaves
room for the 50 ms poll. A recursive Faust definition with no base case
hits `SIGSEGV` inside the worker at this stack size. The receipt is exit
126 `internal`.

## Recorded exclusions

`faust/exclusions/wasm-examples-2.88.0.json` lists five
`physicalModeling/faust-stk` files. Each calls `ffunction` into an STK C
header, which this wasm build cannot link. It also lists the three
multi-file `fastpow2` files above. `compile_source` matches the source
sha256 and raises `CompilerExclusion` before the worker starts. That is
not diagnostic class `other`. The example sources are fetched by
`scripts/fetch-faust-examples.sh` and are not committed.

`CompilerExclusion` on a model output is a failure when rewards land. It
is not a pass, and it is not an ungraded refuge. Reproducing one of these
eight sources must not escape a penalty. Reward behavior is unchanged
until that ladder is built. `CompilerExclusion.reward_disposition` is
`failure`.

Each entry records the raw sha256 and the sha256 after T06 normalization.
T06 forces LF newlines and strips trailing spaces and tabs. Six of the
eight raw hashes will not match that normalized text. Only
`physicalModeling/faust-stk/modalBar.dsp` and `SAM/effects/effects.dsp`
are unchanged. The harness excludes a source when either hash matches, so
those six stay excluded after T06 normalizes them.

## Network namespace on a runner

The compiler runs as `unshare --net --map-current-user`. The uid inside
the namespace is the calling user, not 0, and `CapEff` is 0. A connect
fails with `ENETUNREACH`.

GitHub-hosted Ubuntu sets `kernel.apparmor_restrict_unprivileged_userns=1`.
The pytest job clears that sysctl only when `runner.environment` is
`github-hosted`. The runner is ephemeral.

On a DGX Spark or any self-hosted runner, do not set that sysctl. It is
host-wide and lasts until reboot, and it re-opens unprivileged user
namespaces for every process.

The process that calls `unshare` and writes `uid_map` is `unshare`, not
`node`. Node starts after the namespace exists. A profile on the system
`/usr/bin/unshare` lets every local user create a user namespace, which is
the global sysctl again. A shell wrapper that execs `/usr/bin/unshare` is
the same mistake: AppArmor sees the system binary.

Install a dedicated copy of the unshare binary. It is root-owned, mode
`0750`, group `faustcoder`. The profile is attached to that path only.

```bash
sudo install -d -o root -g root -m 0755 /opt/faustcoder/bin
sudo groupadd --system faustcoder
sudo usermod -aG faustcoder faustcoder
sudo install -o root -g faustcoder -m 0750 "$(command -v unshare)" /opt/faustcoder/bin/fc-unshare
```

`install` copies the binary. Do not replace it with a script.

```text
abi <abi/4.0>,
include <tunables/global>

profile faustcoder-unshare /opt/faustcoder/bin/fc-unshare flags=(unconfined) {
  userns,
}
```

Save that as `/etc/apparmor.d/faustcoder-unshare` and load it with
`apparmor_parser -r`. `flags=(unconfined)` adds `userns` for this path and
does not confine the rest of the process. The `faustcoder` group must
contain only the harness user. Anyone in that group gets unprivileged
user namespaces for any command run through `fc-unshare`, because the
profile is unconfined. Set
`FAUSTCODER_UNSHARE=/opt/faustcoder/bin/fc-unshare` for the harness user.
When that variable is set, the sandbox requires an absolute path to a
regular file that root owns and that group and others cannot write, and
the same for its parent directory. A symlink or a wrapper owned by the
harness user is refused. Inside the compile process, before compiling,
the worker requires `/proc/net/dev` to list only `lo` and requires a
connect to fail. Unset, the sandbox uses the system `unshare`. Either
way, `environment_digest` records that binary's resolved path and sha256.
CI leaves the variable unset and keeps the github-hosted sysctl step.

Confirm, without changing the sysctl:

- as a user who is not in `faustcoder`, `unshare -U true` fails, and
  `/opt/faustcoder/bin/fc-unshare` is not executable
- as the harness user, `fc-unshare --net --map-current-user -- true`
  succeeds
- `unshare -U true` still fails for other users

## Remote imports

A textual `import`, `library` or `component` of an `http://` or `https://`
URL is rejected before the worker starts. The receipt is exit 126,
`internal`, diagnostic `internal: remote import rejected`. The network
namespace is still the control that holds if a later faustwasm build
fetches URLs the filter does not recognize.
