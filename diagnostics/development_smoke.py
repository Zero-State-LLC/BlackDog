"""Bounded default-control impulse checks for pinned pd-faustgen candidates.

This is candidate evidence, not a sealed holdout or production task approval.
Default zero-output and clipping cases retain normal harness failures.
"""

import argparse
import json
from pathlib import Path
from faustcoder import run_signal, ResourceLimits
from faustcoder.signal import SignalProfile, SignalReference
from faustcoder.acquire import git_blob_sha1
from faustcoder.canonical import content_digest_for, sha256_prefixed

# References follow explicit algebra at the source's default control settings.
CONTRACTS = {
    "external/.default.dsp": [1.0],
    "external/examples/dummy.dsp": [2.0, 2.0],
    "external/examples/gain.dsp": [0.0],
    "external/examples/parameters.dsp": [0.0],
    "tests/double.dsp": [0.01],
    "tests/passive.dsp": [0.1 * 0.2 * 0.3 * 0.4],
    "tests/recompile.dsp": [0.2, 0.2],
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--acquisition", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    rows = json.loads((a.acquisition / "receipts.json").read_text())
    results = []
    binding = {
        "acquisition": content_digest_for(rows),
        "contracts": CONTRACTS,
        "driver": sha256_prefixed(Path(__file__).read_bytes()),
        "production_approved": False,
    }
    (a.output / "binding.json").write_text(json.dumps(binding, indent=2))
    for row in rows:
        if row["status"] != "pin_verified":
            continue
        raw = (a.acquisition / (row["blob_sha"] + ".dsp")).read_bytes()
        if git_blob_sha1(raw) != row["blob_sha"]:
            raise ValueError("source pin mismatch")
        amplitudes = CONTRACTS[row["path"]]
        for rate in (44100, 48000):
            profile = SignalProfile(
                sample_rate=rate,
                frames=144000,
                head_frames=144000,
                max_frames=144000,
                stimuli=("impulse",),
                expected_channels=len(amplitudes),
            )
            reference = SignalReference(
                sample_rate=rate,
                block_size=64,
                frames=144000,
                seed=1,
                stimuli=("impulse",),
                channels=len(amplitudes),
                samples={"impulse": [[v] + [0.0] * 143999 for v in amplitudes]},
            )
            run = run_signal(
                raw.decode(), profile, reference, limits=ResourceLimits(timeout_s=60)
            )
            prefix = f"{row['unit_id']}-{rate}"
            evidence = {
                "compiler": run.compilation.receipt,
                "diagnostics": run.compilation.diagnostics,
                "signal": run.receipt,
                "failures": list(run.failures),
            }
            (a.output / (prefix + ".json")).write_text(json.dumps(evidence, indent=2))
            result = {
                "unit_id": row["unit_id"],
                "path": row["path"],
                "rate": rate,
                "compiler_exit": run.compilation.receipt["exit_code"],
                "failures": list(run.failures),
                "passed": run.compilation.receipt["exit_code"] == 0
                and run.receipt is not None
                and not run.failures,
            }
            if result["passed"]:
                bad = SignalReference(
                    sample_rate=rate,
                    block_size=64,
                    frames=144000,
                    seed=1,
                    stimuli=("impulse",),
                    channels=len(amplitudes),
                    samples={
                        "impulse": [[v + 0.1] + [0.0] * 143999 for v in amplitudes]
                    },
                )
                negative = run_signal(
                    raw.decode(), profile, bad, limits=ResourceLimits(timeout_s=60)
                )
                (a.output / (prefix + "-negative.json")).write_text(
                    json.dumps(
                        {
                            "compiler": negative.compilation.receipt,
                            "signal": negative.receipt,
                            "failures": list(negative.failures),
                        },
                        indent=2,
                    )
                )
                result["negative_rejected"] = (
                    negative.compilation.receipt["exit_code"] == 0
                    and "impulse:reference" in negative.failures
                )
                if not result["negative_rejected"]:
                    raise ValueError("corrupted reference was not rejected")
            results.append(result)
            print(result, flush=True)
    (a.output / "summary.json").write_text(
        json.dumps(
            {
                "results": results,
                "production_approved": False,
                "scope": "default-control impulse only; family/dependency/independent review still required",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
