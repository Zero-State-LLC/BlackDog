"""ADVERSARY gate between T06 and the T03 compiler.

The T03 harness bundles faustlibraries ``version.lib`` 2.74.2. The
corpus pin is faustlibraries ``2edec0537f53`` (``version.lib`` 2.80.0).
Those are not the same libraries. T03b stages the corpus pin into the
harness. Until that lands, T06 and T07 do not compile-check corpus
units and do not read compiler receipts as a signal.

``CORPUS_COMPILE_CHECK_ENABLED`` is false. Passing ``compile_check=True``
raises :class:`CompilerGateError` and does not import
``faustcoder.compiler``.
"""

from __future__ import annotations

from faustcoder.errors import DatasetError

CORPUS_COMPILE_CHECK_ENABLED = False
FAUSTLIBRARIES_CORPUS_PIN = "2edec0537f53"
GATE_ID = "T03b"
GATE_MESSAGE = (
    "T03b: corpus compile checks are disabled until faustlibraries "
    f"{FAUSTLIBRARIES_CORPUS_PIN} is staged into the T03 harness. "
    "Compiler receipts are not a T06 or T07 signal."
)


class CompilerGateError(DatasetError):
    """A corpus compile check was requested while T03b is still closed."""


def assert_corpus_compile_disabled(compile_check: bool = False) -> None:
    """Refuse a compile check. The default path does not call the compiler."""
    if compile_check or CORPUS_COMPILE_CHECK_ENABLED:
        raise CompilerGateError(GATE_MESSAGE)
