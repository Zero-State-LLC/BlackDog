"""faustcoder-snapshot exit codes. The fixture fetcher never uses the network."""

from __future__ import annotations

import json
from pathlib import Path

from faustcoder.cli import main

from tests.t06support import (
    ACTOR,
    CREATED_AT,
    PIN,
    REPO,
    cleared,
    inventory_doc,
    notice_doc,
    pins_for,
    stage,
)


def _args(
    tmp_path: Path,
    entries: list[dict[str, object]],
    notices: list[dict[str, object]],
) -> list[str]:
    inventory_path = tmp_path / "inventory.json"
    notice_path = tmp_path / "notice.json"
    inventory_path.write_text(json.dumps(inventory_doc(entries)), encoding="utf-8")
    notice_path.write_text(json.dumps(notice_doc(notices)), encoding="utf-8")
    return [
        "--inventory",
        str(inventory_path),
        "--notice",
        str(notice_path),
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
    stage(root, REPO, PIN, "osc.dsp", data)
    row, notice = cleared("osc", data, path="osc.dsp")
    args = _args(tmp_path, [row], [notice])
    with pins_for(inventory_doc([row]), notice_doc([notice])):
        assert main(args) == 0
        first = capsys.readouterr().out.strip()
        assert len(first) == 7 + 64
        assert main(args) == 0
        assert capsys.readouterr().out.strip() == first


def test_cli_compile_check_and_usage_exit_2(tmp_path: Path, capsys) -> None:
    inventory_path = tmp_path / "inventory.json"
    notice_path = tmp_path / "notice.json"
    inventory_path.write_text("{}", encoding="utf-8")
    notice_path.write_text("{}", encoding="utf-8")
    code = main(
        [
            "--inventory",
            str(inventory_path),
            "--notice",
            str(notice_path),
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
    row, notice = cleared("osc", data, path="missing.dsp")
    args = _args(tmp_path, [row], [notice])
    with pins_for(inventory_doc([row]), notice_doc([notice])):
        assert main(args) == 3
    capsys.readouterr()
    stage(root, REPO, PIN, "osc.dsp", data)
    good_row, good_notice = cleared("osc", data, path="osc.dsp")
    good = _args(tmp_path, [good_row], [good_notice])
    with pins_for(inventory_doc([good_row]), notice_doc([good_notice])):
        assert main(good) == 0
        capsys.readouterr()
        moved = good.copy()
        created = moved.index("--created-at")
        moved[created + 1] = "2026-10-17T20:00:01Z"
        assert main(moved) == 4
