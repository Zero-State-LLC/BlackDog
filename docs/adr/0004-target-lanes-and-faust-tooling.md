# ADR-0004: Target lanes and Faust tooling reuse

Status: ACCEPTED

- Date: 2026-10-16
- Provenance: Danny yes 2026-10-16 23:39 PT ("apply the FaustCoder rework with
  the recommended defaults", plus the plugin and language target class)
- Decides: spec 0.3.0 items 1 to 19 ([spec §19](../../specs/001-faustcoder/spec.md#19-amendments-030-adr-0004-accepted)),
  D-003r2, D-007 to D-012
- Evidence: [research.md](../../specs/001-faustcoder/research.md) F10, F15 to F27, I7 to I9
- Related: [ADR-0002](0002-training-path.md), [ADR-0003](0003-licensing-and-data-rights.md)

## Context

- Faust already ships most of what the 0.2.0 spec planned to build: libfaust
  in WebAssembly with offline rendering (faustwasm), an impulse-response
  regression suite across backends, JSON interface output and a library
  taxonomy. OBSERVED (F15 to F17).
- The owner wants FaustCoder output to run on more than a desktop host:
  embedded boards, plugins, other languages and, later, generic FPGAs.
  OBSERVED (owner brief, 2026-10-16 23:32 and 23:39 PT).
- No vendor-neutral Faust-to-Verilog path works today. OBSERVED (F24, F25).

## Decision

### The model writes Faust; Faust lowers it

FaustCoder generates Faust source for every target. Faust backends
(`-lang`) and `faust2*` scripts produce target code. The model does not write
C++, plugin glue, board code or Verilog directly. INFERRED: keeps one output
language, one corpus and one reward, and reuses maintained generators.

### Harness

| Part | Choice | Replaces |
|---|---|---|
| Compiler | libfaust wasm (faustwasm) in a sandboxed Node.js worker; native Faust 2.88.0 CLI cross-check on a sample and on every promotion candidate | Pinned CLI in a container as the only compiler |
| Render | faustwasm offline render at 44.1 and 48 kHz, fixed block size and seed | Custom render harness |
| Reference check | Impulse-test style comparison with stored references (Faust `tests/impulse-tests`) | Custom spectral checks as the main signal test |
| Graph views | `faust -json`, `-svg`, signal output | Custom parser and typed signal-flow model |
| Diagnostics | Classes `parse_error`, `type_error`, `arity_error`, `warning`, `ok`, `timeout`, `other`; reward ladder parse < type/arity < warnings < clean | Exit code only |

### Target lanes

Every lane runs in a pinned container with no network, writes a
`TargetReceipt` (spec §8) and has known-good and known-bad fixtures.

| Lane | Build | Checks | First targets | Milestone |
|---|---|---|---|---|
| Language (R-024) | `faust -lang <lang>` then that language's compiler | Compiles; compiled run matches the host render | `cpp`, `c`, `rust`, `cmajor` | V0.3 |
| Plugin (R-023) | `faust2clap`; VST3 from the CLAP build via clap-wrapper; `faust2lv2` | `clap-validator`, `pluginval` (VST3), `lv2lint`; parameter map: every Faust UI item appears with the same name, range, default and unit | CLAP, VST3, LV2 on Linux | V0.3 |
| Embedded (R-019) | `faust2daisy`, `faust2teensy` with the board SDK | Builds; flash and RAM from the linker map within budget; CPU budget at the board block size (host proxy until boards exist); real-time safety (R-021) | Daisy, Teensy 4.x | V0.3 |
| FPGA (R-022) | Chosen by the F0 spike | Verilator sim vs Faust render within fixed-point tolerance; Yosys and nextpnr for iCE40 and ECP5; meets audio-rate throughput | iCE40, ECP5 | V0.5-FPGA |

Deferred: AU (needs a macOS runner, Xcode and `auval`; distribution would
need Apple code signing and notarization), `faust2vcvrack`, `faust2max6`,
`faust2puredata`, `faust2supercollider`, ESP32, Bela and OWL. Each is added
through a decision record when needed.

### Plugin SDK choice

- CLAP SDK and clap-helpers: MIT. VST 3 SDK: MIT since 3.8.0. clap-wrapper:
  MIT. OBSERVED (F21, F22).
- VST3 route: default `faust2clap` then clap-wrapper, OBSERVED to build and
  validate on Linux (faust 2.90.10 arch files, faust 2.79.3 compiler), with
  known bugs. See "VST3 route evidence" below. Shipping builds use
  clap-wrapper's linked, self-contained mode (INFERRED from clap-wrapper docs;
  not yet built).
- JUCE is AGPLv3 or commercial. `faust2juce` is the fallback for VST3 only if
  clap-wrapper fails the lane, and only after a commercial JUCE licence
  decision. A DPF (ISC) spike is the second fallback. INFERRED.
- `faust2faustvst` and `faust2vst` target VST2 and are not used. OBSERVED
  (F20).
- `pluginval` is GPL-3.0 and `lv2lint` Artistic-2.0. They run as separate
  validation tools and are not linked into or shipped with FaustCoder output.
  INFERRED; not legal advice.

### VST3 route evidence (amended 0.3.1, Danny yes 2026-10-16 23:56 PT)

Local test on 2026-10-16: a stereo gain (`fixtures/plugin/gain.dsp`) built
with `faust2clap` from the faust checkout at 2.90.10 (`15a26da`), compiled by
faust 2.79.3, then wrapped to VST3 by clap-wrapper (`1cca996`), which fetched
VST 3 SDK `v3.8.0_build_66`. OBSERVED unless marked.

| Route | License fit | Activity (last push) | Faust integration | Headless Linux | LV2 / AU | Result |
|---|---|---|---|---|---|---|
| A. `faust2clap` + clap-wrapper (default) | All MIT; faust `architecture/clap` files carry no license header (open question) | clap-wrapper 2026-10-15; faust CLAP files 2026-07-29 | Built in, one command | Builds with a CXXFLAGS workaround | AU via clap-wrapper on macOS (INFERRED, untested); LV2 via `faust2lv2` | pluginval 1.0.4 strictness 10 SUCCESS (VST3); clap-validator 0.4.1: 33 pass, 2 fail, 1 warning, 8 skipped |
| B. `faust2juce` + JUCE (fallback) | AGPLv3 or commercial | JUCE 2026-10-16 | Mature; VST3, AU, AUv3 by default | Heavier (X11 dev packages); not tested | VST3 + AU in one toolchain | Not built |
| C. DPF (second fallback) | ISC | DPF 2026-10-04; faustpp 2022-09; cookiecutter-dpf-faust 2024-11 | Stale glue | Linux-native (INFERRED) | VST3, CLAP, LV2, AU in one framework (INFERRED) | Not built; spike |
| iPlug2 | Permissive (WDL style) | 2026-09-15 | No faust script | Weak (INFERRED) | No LV2 | Rejected |
| Native Faust VST3 architecture | n/a | n/a | None; `faust2vst`, `faustvst.cpp` are VST2 | n/a | n/a | Not available |

Known issues (route A):

1. Build break on Linux: generated code uses `std::strcmp` without
   `<cstring>`. Workaround: `CXXFLAGS="-include cstring -include cwchar"`.
   The faust2clap README says only the macOS path has been exercised.
2. clap-validator failure: the parameter value after initialization is
   uninitialised (about 3e32) instead of its default 0.
3. clap-validator failure: parameter events with a foreign namespace ID
   change parameter values.
4. clap-validator warning: 4x slowdown on denormals; no flush-to-zero.
5. Licence question for Grame: `architecture/clap/*.cpp` has no license
   header, and those files are compiled into every generated plugin.
6. The test used clap-wrapper's generic mode (the `.vst3` loads `gain.clap`
   from `~/.clap`); the self-contained shipping build is not yet built.
7. Not yet rerun on the pinned faust 2.88.0. AU and LV2 not tested.

CI (`.github/workflows/plugin-lane-smoke.yml`) runs the same build; the strict
CLAP validation step is expected to fail until items 2 and 3 are fixed upstream.

### FPGA F0 spike (only FPGA work scheduled)

- Timebox: 1 week. Inputs: one one-pole low-pass and one sine oscillator.
- Compare three lowerings: (a) repair Faust's VHDL backend (upstream fixes
  allowed, D-011) then `ghdl synth` to Verilog; (b) `-fx` fixed-point C into
  an open HLS tool such as Bambu; (c) a small fixed-point lowering for a
  Faust subset.
- For each: Verilator simulation against the Faust render, Yosys plus
  nextpnr for iCE40 and ECP5, LUT, FF, DSP, BRAM and Fmax, and whether the
  design sustains one sample per channel at 48 kHz.
- Output: a DecisionRecord choosing one path or stopping. The V0.5-FPGA
  lane is planned only after it.

### Version pin set (R-001)

| Component | Pin |
|---|---|
| Faust (native) | 2.88.0 |
| faustlibraries | commit recorded at P0 freeze (2026-10-15 head: `2edec0537f53`) |
| faustwasm | 0.19.0; record the embedded libfaust version in every receipt |
| CLAP SDK, clap-helpers | as vendored by Faust 2.88.0 `faust2clap` |
| clap-wrapper | 0.16.0 |
| VST 3 SDK | latest 3.8.x at lane build time, recorded |
| Validators | clap-validator 0.4.1; pluginval 1.0.4; lv2lint 0.16.2 |
| FPGA tools (spike) | Yosys 0.70, nextpnr 0.11.1, Verilator 5.x, GHDL 5.x |

### Task taxonomy (R-004)

Three axes: DSP category (faustlibraries split), task type (generate,
repair, explain, optimize, remix) and target (host, language, plugin,
embedded, FPGA). Remix tasks combine two or more demos with one experimental
idea; novelty is a dev metric, not a gate (D-010).

## Superseded and removed

History is kept; superseded text stays in its original document with a marker.

- D-003 runtime clause ("DSP target runtimes remain open"): superseded by
  D-003r2.
- Spec §4.2 custom typed signal-flow representation: replaced by compiler
  outputs (spec §19 item 2). §17 S-1 resolved.
- R-004 task list, R-005, R-006 and R-013 wording: replaced or modified
  (spec §19 items 1, 3, 6, 9).
- ADR-0002 P0 "sandboxed compiler harness, signal test harness": now built
  from faustwasm (this ADR).

## Consequences

- P0 shrinks: T03 and T04 wrap faustwasm instead of building a sandbox and
  renderer. INFERRED.
- New tasks T17 to T22 (spec §13). Lanes run beside training and do not block
  P1 or P2; their results become extra rewards after V0.3 (R-016).
- Every lane needs a container image with pinned SDKs; their sizes and build
  times are unknown until built. NOT_COMPUTABLE now.
- Without boards (D-008), CPU budgets for Daisy and Teensy are proxies and are
  labeled INFERRED in receipts until hardware runs exist.

## Alternatives considered

- Model writes target code directly (C++, Verilog): rejected; more output
  languages, smaller per-language data, and no reference semantics to test
  against. INFERRED.
- JUCE for all plugin formats: rejected as default because of AGPLv3 or
  commercial licensing (F22).
- Starting the FPGA lane now: rejected; no working vendor-neutral path
  (F24, F25).
