"""D-013 detectors: header-less files, slices, dedupe, and the eval gate."""

from faustcoder.errors import LicenseEvidenceError
from faustcoder.rights_policy import (
    assert_eval_split_allowed,
    classify_faust_file,
    dedupe_content,
    headerless_findings,
    slice_library,
    strip_cc_todo,
    strictest_license,
)
import pytest


HEADERLESS = 'declare name "plain";\nprocess = _;\n'
STK = 'declare filters_lib_fir_license "MIT-style STK-4.3 license";\n'
MIT_COMMENT = "// Copyright Romain Michon CCRMA/GRAME 2017\n// MIT Licence: https://opensource.org/licenses/MIT\n"
INHERITED = "// Copyright (C) 2003-2023 GRAME, Centre National de Creation Musicale\n// GNU Lesser General Public License\n"


def test_headerless_detector_catches_prefixed_declares_and_comments() -> None:
    assert headerless_findings(HEADERLESS) == []
    assert headerless_findings(INHERITED + HEADERLESS) == []
    assert headerless_findings(STK + "x = 1;\n")
    assert headerless_findings('declare foo copyright "Romain Michon";\n')
    assert headerless_findings('declare foo_author "Romain Michon";\n')
    assert headerless_findings(MIT_COMMENT)
    verdict = classify_faust_file("examples/smartKeyboard/bells.dsp", MIT_COMMENT)
    assert verdict.bucket == "faust-examples-mit"
    assert verdict.license == "MIT"


def test_strictest_license_and_cc_todo_and_slice() -> None:
    assert strictest_license(["STK-4.3", "LGPL-2.1-or-later"]) == "LGPL-2.1-or-later"
    assert strictest_license(["MIT", "BSD"]) == "BSD"
    text = "keep\n// [CCA4I](https://creativecommons.org/licenses/by/4.0/) license (TODO: if/when Romain agrees)\nprocess = 1;\n"
    assert "CCA4I" not in strip_cc_todo(text)
    assert "process = 1;" in strip_cc_todo(text)
    library = """
/* GRAME LICENSE
Copyright (C) 2003-2017 by GRAME
GNU Lesser General Public License
*/
declare kept license "MIT";
declare kept copyright "Copyright Example";
kept = 1;
orphan = 2;
"""
    slices = {item.name: item for item in slice_library(library)}
    assert slices["kept"].decision == "rights_cleared"
    assert slices["kept"].license == "MIT"
    assert slices["orphan"].decision == "rights_cleared"
    assert slices["orphan"].license == "LGPL-2.1-or-later"
    rejected = slice_library("bare = 1;\n", reject_whole=True)
    assert rejected[0].decision == "rights_rejected"
    overloads = slice_library("take(1, xs) = xs;\ntake(n, xs) = xs;\n")
    assert [item.line for item in overloads] == [1, 2]
    assert overloads[0].name == overloads[1].name == "take"


def test_dedupe_and_impulse_eval_gate() -> None:
    exact, stale = dedupe_content(
        {"examples/a.dsp": "aaa"},
        {"src/a.dsp": "aaa", "src/b.dsp": "bbb"},
    )
    assert exact == {"src/a.dsp": "examples/a.dsp"}
    assert stale == ["src/b.dsp"]
    with pytest.raises(LicenseEvidenceError, match="impulse-test"):
        assert_eval_split_allowed(
            "tests/impulse-tests/dsp/constant.dsp",
            "faust-impulse-headerless",
            "eval",
        )
    with pytest.raises(LicenseEvidenceError):
        assert_eval_split_allowed("examples/a.dsp", "faust-impulse-bsd", "holdout")
    assert_eval_split_allowed("examples/a.dsp", "faust-examples-mit", "eval")
