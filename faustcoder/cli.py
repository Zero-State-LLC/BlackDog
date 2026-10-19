"""Command line for the T06 dedup snapshot.

``faustcoder-snapshot`` reads a T05 ``rights-inventory.v1`` document and
a ``notice-manifest.v1`` document, fetches pinned blobs and writes a
``DedupManifest`` into the artifact store. ``--created-at`` is required.
The manifest payload does not contain that timestamp, and a second run
with the same value stores the same envelope bytes. ``generated_at`` on
either document is not part of the manifest digest.

``--compile-check`` defaults to off. Passing it raises the T03b gate
and does not call the compiler. Compiler receipts are not a signal for
this corpus until the pinned faustlibraries are staged into the harness.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from faustcoder.acquire import DirectoryFetcher, GitFetcher, GitHubRawFetcher
from faustcoder.canonical import loads_strict
from faustcoder.compiler_gate import CompilerGateError
from faustcoder.errors import (
    AcquireError,
    ArtifactStoreError,
    CanonicalError,
    DatasetError,
    InventoryError,
    PolicyError,
)
from faustcoder.snapshot import commit_snapshot, compile_snapshot
from faustcoder.store import ArtifactStore

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_ACQUIRE = 3
EXIT_DATASET = 4


def main(argv: Sequence[str] | None = None) -> int:
    """Run one snapshot, or a human-triage sign or submit."""
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] == "triage":
        return _triage_main(raw[1:])
    parser = _parser()
    try:
        args = parser.parse_args(raw)
    except SystemExit as exc:
        code = exc.code
        return EXIT_USAGE if code not in (0, None) else EXIT_OK
    try:
        document = loads_strict(Path(args.inventory).read_text(encoding="utf-8"))
        notice = loads_strict(Path(args.notice).read_text(encoding="utf-8"))
        fetcher = _fetcher(args)
        compiled = compile_snapshot(
            document,
            notice,
            fetcher,
            actor=args.actor,
            created_at=args.created_at,
            compile_check=args.compile_check,
        )
        digest = commit_snapshot(ArtifactStore(args.store), compiled)
    except (CompilerGateError, InventoryError, PolicyError, CanonicalError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    except AcquireError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ACQUIRE
    except (DatasetError, ArtifactStoreError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_DATASET
    print(digest)
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="faustcoder-snapshot")
    parser.add_argument(
        "--inventory",
        required=True,
        help="T05 rights-inventory.v1 JSON",
    )
    parser.add_argument(
        "--notice",
        required=True,
        help="T05 notice-manifest.v1 JSON",
    )
    parser.add_argument("--store", required=True, help="artifact store directory")
    parser.add_argument(
        "--created-at",
        required=True,
        help="UTC RFC3339 timestamp stored on every envelope (YYYY-MM-DDTHH:MM:SSZ)",
    )
    parser.add_argument("--actor", default="faustcoder-snapshot", help="receipt actor")
    parser.add_argument(
        "--fetcher",
        required=True,
        choices=("fixture", "git", "github"),
        help="where pinned blobs are read",
    )
    parser.add_argument(
        "--fixture-root",
        help="root for --fetcher fixture (owner/name/pin/path)",
    )
    parser.add_argument(
        "--git-root",
        action="append",
        default=[],
        metavar="OWNER/NAME=PATH",
        help="local clone for --fetcher git; repeat for each repository",
    )
    parser.add_argument(
        "--compile-check",
        action="store_true",
        help=(
            "disabled by default. T03b: do not compile-check T06 or T07 "
            "corpora, and do not use compiler receipts as a signal, until "
            "faustlibraries 2edec0537f53 is staged into the T03 harness. "
            "Passing this flag raises CompilerGateError and does not call "
            "the compiler."
        ),
    )
    return parser


def _fetcher(args: argparse.Namespace) -> DirectoryFetcher | GitFetcher | GitHubRawFetcher:
    if args.fetcher == "fixture":
        if not args.fixture_root:
            raise ValueError("--fixture-root is required for --fetcher fixture")
        return DirectoryFetcher(args.fixture_root)
    if args.fetcher == "git":
        if not args.git_root:
            raise ValueError("--git-root is required for --fetcher git")
        return GitFetcher(_git_roots(args.git_root))
    if args.git_root or args.fixture_root:
        raise ValueError("--fetcher github does not take a local root")
    return GitHubRawFetcher()


def _triage_main(argv: Sequence[str]) -> int:
    """``triage sign`` writes a drop. ``triage submit`` appends it."""
    parser = argparse.ArgumentParser(prog="faustcoder-snapshot triage")
    sub = parser.add_subparsers(dest="command", required=True)
    sign = sub.add_parser("sign", help="sign a triage statement into a drop file")
    sign.add_argument("--key", required=True, help="Ed25519 private key")
    sign.add_argument("--statement", required=True, help="canonical statement JSON")
    sign.add_argument("--principal", required=True)
    sign.add_argument("--triaged-by", required=True)
    sign.add_argument("--drop", required=True, help="drop file to create")
    submit = sub.add_parser("submit", help="append a signed drop as fc-grader")
    submit.add_argument("--drop", required=True)
    submit.add_argument("--reports", required=True)
    submit.add_argument("--consumed", required=True)
    submit.add_argument("--root-key", required=True)
    submit.add_argument("--run-id", required=True)
    submit.add_argument("--allowed-signers")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        code = exc.code
        return EXIT_USAGE if code not in (0, None) else EXIT_OK
    try:
        if args.command == "sign":
            _triage_sign(args)
        else:
            _triage_submit(args)
    except (OSError, ValueError, CanonicalError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


def _triage_sign(args: argparse.Namespace) -> None:
    from faustcoder.reward.records import RewardRecordError
    from faustcoder.reward.triage_sig import sign_statement, write_drop

    statement = loads_strict(Path(args.statement).read_text(encoding="utf-8"))
    if not isinstance(statement, dict):
        raise ValueError("audit triage statement is not usable")
    try:
        signature = sign_statement(statement, args.key)
        write_drop(
            args.drop,
            principal=args.principal,
            triaged_by=args.triaged_by,
            statement=statement,
            signature=signature,
        )
    except RewardRecordError as exc:
        raise ValueError(str(exc)) from exc


def _triage_submit(args: argparse.Namespace) -> None:
    from faustcoder.reward.audit import AuditReportLog
    from faustcoder.reward.records import (
        ConsumedLog,
        RewardKeyError,
        RewardKeyring,
        RewardRecordError,
        load_root_key,
    )
    from faustcoder.reward.triage_sig import read_drop

    try:
        root = load_root_key(args.root_key)
        drop = read_drop(args.drop)
        record_id = drop.statement.get("record_id")
        triaged_at = drop.statement.get("triaged_at")
        if type(record_id) is not str or type(triaged_at) is not str:
            raise RewardRecordError("audit triage drop file is not usable")
        reports = AuditReportLog(
            args.reports,
            ConsumedLog(args.consumed),
            allowed_signers=args.allowed_signers,
        )
        reports.record_triage(
            RewardKeyring(root, run_id=args.run_id),
            record_id=record_id,
            triaged_by=drop.triaged_by,
            triaged_at=triaged_at,
            drop_path=args.drop,
        )
    except (RewardRecordError, RewardKeyError) as exc:
        raise ValueError(str(exc)) from exc


def _git_roots(entries: Sequence[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for entry in entries:
        repo, separator, path = entry.partition("=")
        if separator != "=" or repo.count("/") != 1 or not path:
            raise ValueError("--git-root must be owner/name=path")
        roots[repo] = Path(path)
    return roots
