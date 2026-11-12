"""Negative controls must be compiler rejections, not harness failures."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "slice2" / "seven_dependencies.py"
_SPEC = importlib.util.spec_from_file_location("seven_dependencies", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

MISSING_LIB = "blackdog_missing_dependency_control.lib"


def test_timeout_receipt_fails_and_missing_dependency_rejection_passes():
    timeout = {"exit_code": 124, "diagnostic_class": "timeout"}
    with pytest.raises(_MODULE.DependencyCheckError, match="harness failure"):
        _MODULE.dependency_rejection(
            timeout,
            "timeout: wall clock limit exceeded\nERROR : unable to open file %s\n" % MISSING_LIB,
            MISSING_LIB,
        )
    for exit_code, diagnostic_class in ((125, "resource_limit"), (126, "internal")):
        with pytest.raises(_MODULE.DependencyCheckError, match="harness failure"):
            _MODULE.dependency_rejection(
                {"exit_code": exit_code, "diagnostic_class": diagnostic_class},
                "ERROR : unable to open file %s\n" % MISSING_LIB,
                MISSING_LIB,
            )
    assert _MODULE.dependency_rejection(
        {"exit_code": 1, "diagnostic_class": "other"},
        "ERROR : unable to open file %s\n" % MISSING_LIB,
        MISSING_LIB,
    )
    assert _MODULE.dependency_rejection(
        {"exit_code": 1, "diagnostic_class": "unbound_symbol"},
        "input:2 : ERROR : undefined symbol : gain\n",
        "gain",
    )
    with pytest.raises(_MODULE.DependencyCheckError, match="did not reject"):
        _MODULE.dependency_rejection(
            {"exit_code": 1, "diagnostic_class": "parse_error"},
            "input:1 : ERROR : syntax error, unexpected ENDDEF\n",
            MISSING_LIB,
        )
