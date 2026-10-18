#!/usr/bin/env python3
"""Cross-arch digest for the nonlinear signal suite.

The script inserts the repository root on sys.path, so it runs without
installing the package:

    python3 scripts/signal_cross_arch.py --out /tmp/signal-arch.json

The same entry point is ``python -m faustcoder.signal_cross_arch`` when
the package is already importable.

Compare two documents, or a fresh render against the committed x86
goldens. A sample mismatch exits 2 and prints infra_fault. The compare
reads the DSP-bank sample hashes, the suite digest and the pinned
flags. It does not change atol or rtol. Node, faustwasm and V8
versions and the stable Node flags are recorded on the document and
are not part of the compare.

    python3 scripts/signal_cross_arch.py --compare a.json b.json
    python3 scripts/signal_cross_arch.py --goldens tests/fixtures/signal/nonlinear-x86-goldens.json

GitHub-hosted CI is x86_64 and has no ARM runner. ``--status`` then
prints pending-dgx-spark. Render the other side on the DGX Spark and
compare it to the committed goldens. See docs/runbooks/signal-harness.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from faustcoder.signal_cross_arch import main

if __name__ == "__main__":
    raise SystemExit(main())
