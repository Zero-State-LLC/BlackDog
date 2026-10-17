"""Rights gate for T06, from the 2026-10-17 defaults and ADR-0003.

This is not a survey and it is not legal advice. The inventory already
names a license and flags. This module refuses a unit whose flags are
looser than that license, or that breaks the impulse and training-only
rules. Unknown license spellings fail the run. They are not guessed
into the allowlist.

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

Impulse units are training-only and cannot be holdout. A unit with
``eligible_for`` of exactly ``train`` must set ``training_only``.
"""

from __future__ import annotations

from collections.abc import Sequence

from faustcoder.errors import PolicyError
from faustcoder.inventory import Unit

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


def assert_clearance(
    license_name: str, eligible_for: Sequence[str], attribution: str
) -> None:
    """Raise unless a rights_cleared guard can write a RightsRecord."""
    maximum = maximum_flags(license_name)
    if maximum is None:
        raise PolicyError("rights_cleared requires an acquirable license")
    if not set(eligible_for) <= maximum:
        raise PolicyError("eligible_for is looser than the license class")
    if "train" not in eligible_for:
        raise PolicyError("an acquired unit must allow training")
    if len(attribution.strip()) < 3:
        raise PolicyError("rights_cleared requires attribution")


def check_unit(unit: Unit) -> None:
    """Apply the defaults to one unit. Rejects are not re-cleared here."""
    if unit.decision == "reject":
        return
    if unit.decision == "vendored":
        _check_vendored(unit)
        return
    if unit.decision not in {"rights_cleared", "training_only"}:
        raise PolicyError(f"{unit.unit_id}: decision is not acquirable")
    _check_acquired(unit)


def _check_vendored(unit: Unit) -> None:
    if unit.eligible_for or unit.training_only or unit.impulse or unit.holdout:
        raise PolicyError(f"{unit.unit_id}: a vendored copy is not cleared on its own")
    if unit.notice is not None or unit.upstream_unit_id is None:
        raise PolicyError(f"{unit.unit_id}: vendored units name an upstream and no notice")


def _check_acquired(unit: Unit) -> None:
    kind = license_class(unit.license)
    if kind in {"excluded", "unrecognized"}:
        raise PolicyError(f"{unit.unit_id}: license cannot be acquired")
    if unit.decision == "training_only" and kind == "permissive":
        pass
    flags = frozenset(unit.eligible_for)
    maximum = maximum_flags(unit.license)
    assert maximum is not None
    if unit.decision == "training_only" or unit.impulse:
        maximum = frozenset({"train"})
    if not flags <= maximum:
        raise PolicyError(f"{unit.unit_id}: flags are looser than the license class")
    if "train" not in flags:
        raise PolicyError(f"{unit.unit_id}: an acquired unit must allow training")
    if unit.training_only != (flags == frozenset({"train"})):
        raise PolicyError(f"{unit.unit_id}: training_only does not match eligible_for")
    if unit.impulse:
        if unit.decision != "training_only" or unit.holdout or flags != frozenset({"train"}):
            raise PolicyError(
                f"{unit.unit_id}: impulse tests are training-only and never eval or holdout"
            )
    if unit.holdout and unit.impulse:
        raise PolicyError(f"{unit.unit_id}: impulse tests never enter holdout")
    if len(unit.attribution.strip()) < 3:
        raise PolicyError(f"{unit.unit_id}: acquired units need attribution")
    if unit.notice is None:
        raise PolicyError(f"{unit.unit_id}: acquired units need notice linkage")
    if "redistribute" in flags and unit.notice.copyright.strip() == "":
        raise PolicyError(f"{unit.unit_id}: redistribution needs a copyright notice")
