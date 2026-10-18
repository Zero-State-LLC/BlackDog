"""Command line for the nonlinear-suite cross-arch digest.

``python -m faustcoder.signal_cross_arch`` works when this package is
importable. ``scripts/signal_cross_arch.py`` inserts the repo root on
``sys.path`` first, so it also runs from a checkout that has not been
installed.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from faustcoder.signal_suite import compare_arch_documents, cross_arch_status, render_arch_document


def _load(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise SystemExit("arch document must be a JSON object")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="render this machine and write a document")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("LEFT", "RIGHT"))
    parser.add_argument(
        "--goldens",
        type=Path,
        help="compare --out, or the following document, to committed x86 goldens",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="print pending-dgx-spark or pending-x86 when the other arch is absent",
    )
    args = parser.parse_args(argv)
    if args.status:
        print(cross_arch_status(platform.machine(), None))
        return 0
    if args.compare is not None:
        result = compare_arch_documents(_load(args.compare[0]), _load(args.compare[1]))
        return _finish(result)
    if args.out is None and args.goldens is None:
        parser.error("pass --out, --compare, --goldens, or --status")
    document = render_arch_document()
    if args.out is not None:
        args.out.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(document["arch"])
        print(document["test_suite_digest"])
    if args.goldens is not None:
        result = compare_arch_documents(document, _load(args.goldens))
        return _finish(result)
    return 0


def _finish(result: str) -> int:
    print(result)
    if result == "infra_fault":
        print(
            "cross-arch sample mismatch is an infrastructure fault; "
            "tolerances were not changed",
            file=sys.stderr,
        )
        return 2
    return 0
