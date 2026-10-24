# Shipwright candidate qualification — 2026-10-24

Five programs were statically extracted from dinger086/shipwright-audio at eef7b31e2b82974172d8c562412069624861950a, instruments.py blob bbb0a0d2fe0256de0ebedc1c42c715f734250d63. Extraction interprets only string literals, concatenation, and numeric default substitutions; upstream Python is never executed. Fetch the pinned source into work/shipwright-instruments.py before running the retained builder. Default cutoff/wet values are part of these diagnostic identities. The library pin 2edec0537f536eaa130d42c354884d7db971663c is explicitly chosen for diagnostics; the upstream import is unpinned.

| Candidate | Dependency names / exact spans | Native closure comparison | Semantic status |
|---|---:|---|---|
| saw_lead | 17 / 26 | Four rates pass | Bounded default controls and gate transition only |
| soft_pad | 21 / 31 | Four rates pass | Bounded default controls and gate transition only |
| sub_bass | 34 / 53 | Four rates pass | Bounded default controls and gate transition only |
| pluck | 23 / 24 | Four rates pass with external excitation | Blocked: one audio input; wrong intended parameter mapping |
| reverb | 6 / 6 | Four rates pass | Bounded impulse plus sine inputs only |

All 140 span occurrences were verified against their pinned Git blob and byte-range hashes. No lexical dependencies remain unresolved. Independent local verification checked 40 finite nonzero captures, 20 byte-identical original/closed pairs, four rates (44100/48000/96000/192000), and five missing-platform compile failures. Each render contains 24000 frames. Native compilation uses single precision, ftz=0, GCC -O1, contraction disabled and no fast math; the existing per-child limits remain 20 CPU seconds, 1 GiB address space, 16 MiB output and 30 seconds wall time. No WASM, arbitrary controls, long decay, perceptual equivalence or production approval is claimed.

The first runtime check deliberately expected zero instrument inputs and rejected pluck. Inspection of both generated interfaces found one input. At the pinned library, pm.ks(length,damping,excitation) takes three arguments; upstream pm.ks(freq,gate) binds frequency to physical length and gate to damping, leaving excitation as an external audio input. The final diagnostic supplies that input solely to establish closure equivalence, and explicitly retains instrument_interface_pass=false. A corrected instrument requires a new target/context contract with a frequency-to-length conversion, damping choice and excitation semantics; original equivalence does not authorize silently substituting it.

The two missing per-function notices, ro.interleave and pm.chain, were added under existing D-013 delegation from the exact pinned LGPL library headers, covering all selected overloads. No unresolved library notice remains. Source eligibility stays training-only wherever LGPL applies; the compiled-code exception does not grant evaluation-source admission. Root MIT and unchanged dependency notices do not establish source-specific teacher provenance or canonical admission.

The pinned README and the two returned path-history commits (c7556e3cad7d96eae10f21d77308881180103819 and 0f54c82be8c748e83a9ec3a7a33e1423ab0f7290) did not identify an exact contributing model/version. This limited search does not prove human-only authorship. The separate Designing Sound provenance issue remains open with zero comments: <https://github.com/materializepath/designing-sound-experiments/issues/1>.

Full family replay retained the earlier originals and repaired Bouncing Ball identity and added all five Shipwright full closures: 1545 identities, 12 components, 30047 joining operations under the unchanged policy. All five are comparison-connected. None is eligible as an independent evaluation candidate.

The exact ds.mulk review packet and readiness validator were replayed after the notice updates. All 61 relevant review, readiness and rights tests passed. PR #115 still has zero reviews. The scoped mailbox search returned zero results, and the public Spark custody scan is byte-identical to the preceding scan. No authenticated signed T07 snapshot, trusted custodian key binding or scoped signed readiness package was newly found. Independent semantic review and canonical admission remain pending. pilot_ready=false and training_authorized=false.

The binary evidence archive is retained locally at work/shipwright-evidence.tar.gz; its SHA-256 is bound in shipwright-verification-2026-10-24.json. Full extracted library source is not added to the repository. These scripts follow the existing work-directory diagnostic workflow and depend on the retained pinned library cache and earlier population/runner scripts.
