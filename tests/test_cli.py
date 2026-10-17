"""faustcoder-snapshot exit codes. The fixture fetcher never uses the network."""

from __future__ import annotations

import json
from pathlib import Path

from faustcoder.cli import main

from tests.t06support import ACTOR, CREATED_AT, PIN, REPO, inventory, stage, stage_notice, unit


def _args(tmp_path: Path, document: dict[str, object]) -> list[str]:
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(document), encoding="utf-8")
    return [
        "--inventory",
        str(inventory_path),
        "--store",
        str(tmp_path / "store"),
        "--created-at",
        CREATED_AT,
        "--actor",
        ACTOR,
        "--fetcher",
        "fixture",
        "--fixture-root",
        str(tmp_path / "fixtures"),
    ]


def test_cli_prints_the_digest_and_a_repeat_is_idempotent(tmp_path: Path, capsys) -> None:
    data = b"process = 1;\n"
    root = tmp_path / "fixtures"
    stage_notice(root)
    stage(root, REPO, PIN, "osc.dsp", data)
    args = _args(tmp_path, inventory([unit("osc", data, path="osc.dsp")]))
    assert main(args) == 0
    first = capsys.readouterr().out.strip()
    assert len(first) == 7 + 64
    assert main(args) == 0
    assert capsys.readouterr().out.strip() == first


def test_cli_compile_check_and_usage_exit_2(tmp_path: Path, capsys) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text("{}", encoding="utf-8")
    code = main(
        [
            "--inventory",
            str(inventory_path),
            "--store",
            str(tmp_path / "store"),
            "--created-at",
            CREATED_AT,
            "--fetcher",
            "fixture",
            "--fixture-root",
            str(tmp_path),
            "--compile-check",
        ]
    )
    assert code == 2
    assert "T03b" in capsys.readouterr().err
    assert main(["--inventory", str(inventory_path)]) == 2


def test_cli_acquire_and_store_exit_codes(tmp_path: Path, capsys) -> None:
    data = b"process = 1;\n"
    root = tmp_path / "fixtures"
    stage_notice(root)
    args = _args(tmp_path, inventory([unit("osc", data, path="missing.dsp")]))
    assert main(args) == 3
    capsys.readouterr()
    stage(root, REPO, PIN, "osc.dsp", data)
    good = _args(tmp_path, inventory([unit("osc", data, path="osc.dsp")]))
    assert main(good) == 0
    capsys.readouterr()
    moved = good.copy()
    created = moved.index("--created-at")
    moved[created + 1] = "2026-10-17T20:00:01Z"
    assert main(moved) == 4
