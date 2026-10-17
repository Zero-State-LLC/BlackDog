"""Recorded 2026-10-17 license classes. Not a rights guard.

T05 (``faustcoder.rights``) is the only component that clears or
rejects a unit. This module does not write a RightsRecord, does not
emit ``rights_cleared``, and the snapshot does not call it to admit a
row. ``ordered_flags`` only sorts an intersection the snapshot already
computed. The tables below record the defaults so a later pin of the
T05 inventory can be read against the same spellings. They are not
legal advice.

Maximum flags:

- MIT, MIT-0, BSD-1/2/3/4-Clause, 0BSD, Apache-2.0, ISC, Unlicense,
  CC0-1.0, BSL-1.0, Zlib and STK-4.3: train, eval, redistribute.
  Redistribution still needs notice linkage, which the inventory
  contract requires for every acquired unit.
- The exact string ``BSD`` (no clause): train and eval, never
  redistribute.
- GPL and LGPL spellings listed below, including the Faust library
  exception: train only.
- AGPL, MPL-2.0, CC-BY-NC-SA-4.0, ``unlicensed``, ``unknown`` and
  ``NONE``: not acquired.

The snapshot does not re-apply this table. A cleared T05 row is
admitted with the flags that row already carries.
"""

from __future__ import annotations

from collections.abc import Sequence

_FLAG_ORDER = ("train", "eval", "redistribute")
_PERMISSIVE = frozenset(
    {
        "MIT",
        "MIT-0",
        "BSD-1-Clause",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSD-4-Clause",
        "0BSD",
        "Apache-2.0",
        "ISC",
        "Unlicense",
        "CC0-1.0",
        "BSL-1.0",
        "Zlib",
        "STK-4.3",
    }
)
_TRAIN_ONLY = frozenset(
    {
        "GPL",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "GPL2+",
        "GPLv3",
        "GPL v3",
        "LGPL",
        "LGPL-2.0-only",
        "LGPL-2.1",
        "LGPL-2.1-only",
        "LGPL-2.1-or-later",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "LGPLv2.1",
        "LGPL with exception",
        "LicenseRef-LGPL-2.1-or-later-with-Faust-exception",
    }
)
_EXCLUDED = frozenset(
    {
        "AGPL",
        "AGPL-1.0-only",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "MPL-2.0",
        "CC-BY-NC-SA-4.0",
        "unlicensed",
        "unknown",
        "NONE",
    }
)
_FULL = frozenset({"train", "eval", "redistribute"})
_BARE_BSD = frozenset({"train", "eval"})
_TRAIN = frozenset({"train"})


def ordered_flags(flags: Sequence[str] | frozenset[str]) -> list[str]:
    """Return flags in train, eval, redistribute order."""
    present = set(flags)
    return [flag for flag in _FLAG_ORDER if flag in present]


def license_class(license_name: str) -> str:
    """Return ``permissive``, ``bare_bsd``, ``train_only``, ``excluded`` or ``unrecognized``."""
    if license_name in _PERMISSIVE:
        return "permissive"
    if license_name == "BSD":
        return "bare_bsd"
    if license_name in _TRAIN_ONLY or license_name.startswith("AGPL"):
        if license_name.startswith("AGPL"):
            return "excluded"
        return "train_only"
    if license_name in _EXCLUDED:
        return "excluded"
    return "unrecognized"


def maximum_flags(license_name: str) -> frozenset[str] | None:
    """Return the widest legal flag set, or ``None`` when the license is not acquirable."""
    kind = license_class(license_name)
    if kind == "permissive":
        return _FULL
    if kind == "bare_bsd":
        return _BARE_BSD
    if kind == "train_only":
        return _TRAIN
    return None


