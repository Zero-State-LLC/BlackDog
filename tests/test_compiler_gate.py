"""T03b: T06 does not compile corpora and does not import the compiler."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from faustcoder.compiler import FAUSTLIBRARIES_PIN
from faustcoder.compiler_gate import (
    CORPUS_COMPILE_CHECK_ENABLED,
    FAUSTLIBRARIES_CORPUS_PIN,
    CompilerGateError,
    assert_corpus_compile_disabled,
)
from faustcoder.snapshot import compile_snapshot

T06_MODULES = (
    "faustcoder/acquire.py",
    "faustcoder/cli.py",
    "faustcoder/compiler_gate.py",
    "faustcoder/dataset.py",
    "faustcoder/inventory.py",
    "faustcoder/neardup.py",
    "faustcoder/normalize.py",
    "faustcoder/policy.py",
    "faustcoder/snapshot.py",
)


def test_gate_is_closed_and_names_the_corpus_pin() -> None:
    assert CORPUS_COMPILE_CHECK_ENABLED is False
    assert FAUSTLIBRARIES_CORPUS_PIN == FAUSTLIBRARIES_PIN == "2edec0537f53"
    assert_corpus_compile_disabled(False)
    with pytest.raises(CompilerGateError, match="T03b"):
        assert_corpus_compile_disabled(True)


def test_t06_modules_do_not_import_the_compiler_or_the_sandbox() -> None:
    for relative in T06_MODULES:
        tree = ast.parse(Path(relative).read_text(encoding="utf-8"))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        banned = [
            name
            for name in modules
            if name == "faustcoder.compiler"
            or name.startswith("faustcoder.compiler.")
            or name == "faustcoder.sandbox"
            or name.startswith("faustcoder.sandbox.")
        ]
        assert banned == [], relative


def test_compile_check_raises_before_fetch() -> None:
    class _Fetcher:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            raise AssertionError("fetch")

    with pytest.raises(CompilerGateError, match="2edec0537f53"):
        compile_snapshot(
            {},
            {},
            _Fetcher(),
            actor="snapshot-bot",
            created_at="2026-10-17T20:00:00Z",
            compile_check=True,
        )
