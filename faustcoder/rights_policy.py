"""License classification helpers for the dataset rights machine.

D-013 (Danny yes 2026-10-17 1:04 PM PT) is the policy. This module does
not store program text. Scanners keep source trees outside the repo and
pass only metadata back.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

from faustcoder.errors import LicenseEvidenceError

REVIEWER_BOOF = "Boof (delegated by Danny 2026-10-17)"
_PLACEHOLDERS = frozenset(
    {
        "n/a",
        "na",
        "n.a.",
        "none",
        "unknown",
        "tbd",
        "todo",
        "x",
        "xx",
        "-",
        "--",
        "null",
        "placeholder",
    }
)
_COMMIT_IN_URI = re.compile(r"(?:^|[/=])([0-9a-f]{40})(?:[/=]|$)")
_BRANCH_URI = re.compile(r"/tree/(?:main|master)(?:/|$)")
_DECLARE = re.compile(
    r'(?m)^[ \t]*declare[ \t]+([A-Za-z_][A-Za-z0-9_]*)'
    r'(?:[ \t]+(licen[cs]e|copyright|author))?[ \t]+"(.*?)"[ \t]*;'
)
_FUNC = re.compile(
    r"(?m)^([A-Za-z_][A-Za-z0-9_]*)[ \t]*(\([^;\n]*\))?[ \t]*=[ \t]*(.*)$"
)
_CC_TODO = re.compile(r"CCA4I|TODO:\s*if/when Romain agrees", re.IGNORECASE)
_NOTICE = re.compile(
    r"copyright|licen[cs]e|\bgpl\b|\bnc\b|non-commercial|\bmit\b|\bbsd\b|\bstk\b",
    re.IGNORECASE,
)
_THIRD_PARTY_MARKER = re.compile(
    r"\bmit\b|\bbsd\b|\bstk\b|non-commercial|\bnc\b|cc-by-nc",
    re.IGNORECASE,
)
_BOILERPLATE = (
    re.compile(r"copyright\s*\(c\).*(grame|inria|centre national)", re.IGNORECASE),
    re.compile(r"gnu lesser general public license|\blgpl\b", re.IGNORECASE),
    re.compile(r"this program is free software", re.IGNORECASE),
    re.compile(r"merchantability|fitness for a particular purpose", re.IGNORECASE),
    re.compile(r"free software foundation", re.IGNORECASE),
    re.compile(r"exception to the lgpl|larger faust program", re.IGNORECASE),
    re.compile(r"grame license", re.IGNORECASE),
)
_GRAME_HOLDER = re.compile(r"grame|inria|centre national", re.IGNORECASE)
_PERSON = re.compile(
    r"michon|smith|shekar|meyer|warden|degert|shorthose|larkin|rateau|"
    r"lebreton|orlarey|jos\b",
    re.IGNORECASE,
)

# Canonical names. Bare "BSD" is not a clause variant.
_PERMISSIVE = {
    "MIT": "MIT",
    "MIT-0": "MIT-0",
    "MIT License (MIT)": "MIT",
    "MIT Licence": "MIT",
    "BSD-1-Clause": "BSD-1-Clause",
    "BSD-2-Clause": "BSD-2-Clause",
    "BSD-3-Clause": "BSD-3-Clause",
    "BSD-4-Clause": "BSD-4-Clause",
    "0BSD": "0BSD",
    "Apache-2.0": "Apache-2.0",
    "Apache License, Version 2.0": "Apache-2.0",
    "ISC": "ISC",
    "Unlicense": "Unlicense",
    "STK-4.3": "STK-4.3",
    "LicenseRef-STK-4.3": "STK-4.3",
    "MIT-style STK-4.3 license": "STK-4.3",
}
_BARE_BSD = {"BSD": "BSD"}
_TRAIN_ONLY = {
    "GPL": "GPL",
    "GPL v3": "GPL v3",
    "GPL2+": "GPL2+",
    "GPLv3": "GPLv3",
    "GPL-2.0-only": "GPL-2.0-only",
    "GPL-2.0-or-later": "GPL-2.0-or-later",
    "GPL-3.0-only": "GPL-3.0-only",
    "GPL-3.0-or-later": "GPL-3.0-or-later",
    "LGPL": "LGPL",
    "LGPL-2.1": "LGPL-2.1",
    "LGPLv2.1": "LGPLv2.1",
    "LGPL-2.0-only": "LGPL-2.0-only",
    "LGPL-2.1-only": "LGPL-2.1-only",
    "LGPL-2.1-or-later": "LGPL-2.1-or-later",
    "LGPL-3.0-only": "LGPL-3.0-only",
    "LGPL-3.0-or-later": "LGPL-3.0-or-later",
    "LGPL with exception": "LGPL with exception",
    "LicenseRef-LGPL-2.1-or-later-with-Faust-exception": (
        "LicenseRef-LGPL-2.1-or-later-with-Faust-exception"
    ),
}
_REJECTED = {
    "unlicensed": "unlicensed",
    "unknown": "unknown",
    "NONE": "NONE",
    "AGPL": "AGPL",
    "AGPL-1.0-only": "AGPL-1.0-only",
    "AGPL-3.0-only": "AGPL-3.0-only",
    "AGPL-3.0-or-later": "AGPL-3.0-or-later",
    "CC-BY-NC-SA-4.0": "CC-BY-NC-SA-4.0",
    "vendored-duplicate": "vendored-duplicate",
}
TRAIN_ONLY = ("train",)
TRAIN_EVAL = ("train", "eval")
REDISTRIBUTABLE = ("train", "eval", "redistribute")


@dataclass(frozen=True)
class LicenseClassification:
    """Policy class for one license string. Not legal advice."""

    decision: str
    eligible_for: tuple[str, ...]
    canonical_license: str
    rationale: str
    redistribute: bool


@dataclass(frozen=True)
class Declare:
    """One parsed declare. ``owner`` is None for a file-level declare."""

    owner: str | None
    kind: str
    value: str


@dataclass(frozen=True)
class FunctionSlice:
    """Metadata for one library function. The body is not retained.

    ``line`` is 1-based. Pattern-match overloads share ``name`` and are
    distinguished by line when an inventory key is built.
    """

    name: str
    line: int
    license: str
    copyright: str
    decision: str
    eligible_for: tuple[str, ...]
    redistribute: bool
    source: str
    stripped_sha256: str


@dataclass(frozen=True)
class FileVerdict:
    """How one Faust file is bucketed. Copyright is metadata, not source."""

    bucket: str
    license: str
    decision: str
    evidence_label: str
    copyright: str
    redistribute: bool
    eligible_for: tuple[str, ...]
    headerless: bool
    findings: tuple[str, ...]


def classify_license(license_name: str) -> LicenseClassification:
    """Classify one license string under D-004, D-007, and D-013."""
    if not isinstance(license_name, str) or not license_name.strip():
        raise LicenseEvidenceError("license evidence has no license name")
    name = license_name.strip()
    if name in _PERMISSIVE:
        return LicenseClassification(
            "rights_cleared",
            REDISTRIBUTABLE,
            _PERMISSIVE[name],
            "D-004/D-013 allowlist: train, eval, and redistribute with NOTICE",
            True,
        )
    if name in _BARE_BSD:
        return LicenseClassification(
            "rights_cleared",
            TRAIN_EVAL,
            _BARE_BSD[name],
            "D-013: bare BSD is train and eval only; the clause text is missing",
            False,
        )
    if name in _TRAIN_ONLY:
        return LicenseClassification(
            "rights_cleared",
            TRAIN_ONLY,
            _TRAIN_ONLY[name],
            "D-004/D-007: training only; do not redistribute the source",
            False,
        )
    if name in _REJECTED:
        return LicenseClassification(
            "rights_rejected",
            (),
            _REJECTED[name],
            "D-004/D-007: ineligible, unknown, or restricted",
            False,
        )
    return LicenseClassification(
        "needs_human",
        (),
        name,
        "license is not in the accepted allowlist, training-only set, or exclusion set",
        False,
    )


def same_license(left: str, right: str) -> bool:
    """True when both strings canonicalize to one policy license."""
    return (
        classify_license(left).canonical_license
        == classify_license(right).canonical_license
    )


def is_placeholder(value: object) -> bool:
    """True for empty attribution and for tokens such as ``n/a``."""
    if not isinstance(value, str):
        return True
    text = value.strip()
    if len(text) < 3:
        return True
    return text.casefold() in _PLACEHOLDERS


def valid_actor(actor: object) -> bool:
    """A transition actor is a short name, not a one-letter placeholder."""
    if not isinstance(actor, str):
        return False
    text = actor.strip()
    if len(text) < 3 or len(text) > 200:
        return False
    if text.casefold() in _PLACEHOLDERS:
        return False
    return re.search(r"[A-Za-z]", text) is not None


def commit_in_uri(uri: object) -> str | None:
    """Return the 40-hex commit in ``uri``, or None for a branch URL."""
    if not isinstance(uri, str):
        return None
    if _BRANCH_URI.search(uri):
        return None
    match = _COMMIT_IN_URI.search(uri)
    if match is None:
        return None
    return match.group(1)


def is_impulse_path(path: str = "", entry_id: str = "") -> bool:
    """Impulse-test material is training-only and never an eval item."""
    return "impulse-tests" in path or entry_id.startswith("faust-impulse-")


def assert_eval_split_allowed(
    path: str = "",
    entry_id: str = "",
    split: str = "",
) -> None:
    """Refuse eval and holdout for impulse-test files (D-013)."""
    if is_impulse_path(path, entry_id) and split in {"eval", "holdout", "sealed"}:
        raise LicenseEvidenceError(
            "impulse-test files cannot enter the eval split or the sealed holdout"
        )


def overlay_eligible(
    classification: LicenseClassification,
    *,
    path: str = "",
    entry_id: str = "",
) -> tuple[str, ...]:
    """Apply the impulse and redistribution caps to a license class."""
    allowed = list(classification.eligible_for)
    if is_impulse_path(path, entry_id):
        allowed = [item for item in allowed if item == "train"]
    if not classification.redistribute:
        allowed = [item for item in allowed if item != "redistribute"]
    return tuple(allowed)


def strictest_license(names: list[str]) -> str:
    """Return the canonical license that wins inside one mixed file."""
    if not names:
        raise LicenseEvidenceError("strictest-license comparison has no licenses")
    ranked = [classify_license(name) for name in names]
    rejected = [item for item in ranked if item.decision == "rights_rejected"]
    if rejected:
        return rejected[0].canonical_license
    unknown = [item for item in ranked if item.decision == "needs_human"]
    if unknown:
        return unknown[0].canonical_license
    train_only = [item for item in ranked if item.eligible_for == TRAIN_ONLY]
    if train_only:
        return train_only[0].canonical_license
    bare = [item for item in ranked if not item.redistribute]
    if bare:
        return bare[0].canonical_license
    return ranked[0].canonical_license


def strip_cc_todo(text: str) -> str:
    """Drop ungranted CCA4I TODO comments. Other lines stay."""
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if _CC_TODO.search(line) is None
    )


def content_sha256(data: bytes) -> str:
    """SHA-256 of file bytes. This is the dedupe key, not a git blob id."""
    return hashlib.sha256(data).hexdigest()


def dedupe_content(
    upstream: Mapping[str, str], vendored: Mapping[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Match vendored paths to upstream paths by content hash.

    ``upstream`` and ``vendored`` map a repo-relative path to the sha256
    of the file bytes. The first return value maps a vendored path to the
    upstream path with the same bytes. The second is the stale remainder.
    """
    by_hash: dict[str, str] = {}
    for path, digest in upstream.items():
        by_hash.setdefault(digest, path)
    exact: dict[str, str] = {}
    stale: list[str] = []
    for path, digest in vendored.items():
        match = by_hash.get(digest)
        if match is None:
            stale.append(path)
        else:
            exact[path] = match
    return exact, stale


def parse_declares(text: str) -> list[Declare]:
    """Parse file-level and ``declare <fn> <key>`` metadata."""
    found: list[Declare] = []
    for match in _DECLARE.finditer(text):
        name, key, value = match.group(1), match.group(2), match.group(3)
        value = " ".join(value.split())
        if key in {"license", "licence", "copyright", "author"}:
            kind = "license" if key.startswith("licen") else key
            found.append(Declare(name, kind, value))
            continue
        for suffix, kind in (
            ("_license", "license"),
            ("_licence", "license"),
            ("_copyright", "copyright"),
            ("_author", "author"),
        ):
            if name.endswith(suffix):
                found.append(Declare(name[: -len(suffix)] or None, kind, value))
                break
        else:
            if name in {"license", "licence", "copyright", "author"}:
                kind = "license" if name.startswith("licen") else name
                found.append(Declare(None, kind, value))
    return found


def leading_comment_text(text: str) -> str:
    """Return the comment block before the first code line."""
    lines: list[str] = []
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_block:
            lines.append(line)
            if "*/" in stripped:
                in_block = False
            continue
        if not stripped:
            if lines:
                lines.append(line)
            continue
        if stripped.startswith("//"):
            lines.append(line)
            continue
        if stripped.startswith("/*"):
            lines.append(line)
            if "*/" not in stripped:
                in_block = True
            continue
        break
    return "\n".join(lines)


def non_inherited_notices(text: str) -> list[str]:
    """Comment notices that are not the Faust repository LGPL grant."""
    findings: list[str] = []
    for line in leading_comment_text(text).splitlines():
        if _NOTICE.search(line) is None:
            continue
        inherited = any(pattern.search(line) for pattern in _BOILERPLATE)
        if inherited and _THIRD_PARTY_MARKER.search(line) is None:
            continue
        findings.append(line.strip()[:180])
    return findings


def _grame_only(value: str) -> bool:
    return _GRAME_HOLDER.search(value) is not None and _PERSON.search(value) is None


def _inherited_license(value: str) -> bool:
    """True for the Faust repository LGPL grant, not for GPL."""
    try:
        classified = classify_license(value)
    except LicenseEvidenceError:
        return False
    return "LGPL" in classified.canonical_license.upper()


def headerless_findings(text: str) -> list[str]:
    """Reasons a file is not header-less. An empty list means header-less.

    A file-level ``declare author`` does not disqualify. Prefixed
    ``*_license``, ``*_copyright``, and ``*_author`` declares do, unless
    the license and copyright are only the inherited GRAME or INRIA LGPL
    grant.
    """
    declares = parse_declares(text)
    findings = [f"comment: {line}" for line in non_inherited_notices(text)]
    licenses = [item for item in declares if item.kind == "license"]
    inherited_only = bool(licenses) and all(
        _inherited_license(item.value) for item in licenses
    )
    for item in licenses:
        if _inherited_license(item.value):
            continue
        owner = item.owner or "file"
        findings.append(f"declare {owner} license: {item.value[:120]}")
    if inherited_only:
        return findings
    for item in declares:
        if item.kind == "author" and item.owner is None:
            continue
        if item.kind == "license":
            continue
        if item.kind == "copyright" and _grame_only(item.value):
            continue
        if item.kind == "author" and _grame_only(item.value):
            continue
        if item.kind in {"copyright", "author"}:
            owner = item.owner or "file"
            findings.append(f"declare {owner} {item.kind}: {item.value[:120]}")
    return findings


def _copyright_from(text: str, declares: list[Declare]) -> str:
    values = [item.value for item in declares if item.kind == "copyright"]
    if not values:
        values = [
            line.strip().lstrip("/").strip()
            for line in leading_comment_text(text).splitlines()
            if re.search(r"copyright", line, re.IGNORECASE)
        ]
    if not values:
        authors = [item.value for item in declares if item.kind == "author"]
        values = authors[:1]
    joined = "; ".join(dict.fromkeys(values))
    return joined[:500]


def _jos_copyright(declares: list[Declare], found: str) -> str:
    """D-013 maps author JOS to Julius O. Smith III. The mapping is INFERRED."""
    authors = " ".join(item.value for item in declares if item.kind == "author")
    if re.search(r"\bJOS\b", authors) and "Julius" not in found:
        extra = "Julius O. Smith III (INFERRED from author JOS)"
        return f"{found}; {extra}" if found else extra
    return found


def classify_faust_file(path: str, text: str) -> FileVerdict:
    """Bucket one Faust example or impulse file. Not used for .lib slicing."""
    declares = parse_declares(text)
    copyright = _jos_copyright(declares, _copyright_from(text, declares))
    findings = tuple(headerless_findings(text))
    licenses = [item.value for item in declares if item.kind == "license"]
    comments = leading_comment_text(text)
    if not any(not _inherited_license(value) for value in licenses) and re.search(
        r"\bMIT\b", comments
    ):
        licenses.append("MIT")
    foreign = [value for value in licenses if not _inherited_license(value)]
    if not findings and not foreign:
        bucket = (
            "faust-impulse-headerless"
            if "impulse-tests" in path
            else "faust-examples-headerless"
        )
        return FileVerdict(
            bucket,
            "LGPL-2.1-or-later",
            "needs_human",
            "INFERRED",
            copyright,
            False,
            (),
            True,
            (),
        )
    if path.endswith("examples/misc/guitarix.dsp"):
        return FileVerdict(
            "faust-examples-guitarix",
            "GPL-2.0-or-later",
            "rights_cleared",
            "OBSERVED",
            copyright or "Hermann Meyer, James Warden, Andreas Degert, Pete Shorthose",
            False,
            TRAIN_ONLY,
            False,
            findings,
        )
    if not licenses:
        bucket = (
            "faust-impulse-copyright-only"
            if "impulse-tests" in path
            else "faust-examples-copyright-only"
        )
        return FileVerdict(
            bucket,
            "unlicensed",
            "needs_human",
            "INFERRED",
            copyright,
            False,
            (),
            False,
            findings,
        )
    canonical = strictest_license(licenses)
    classified = classify_license(canonical)
    eligible = overlay_eligible(classified, path=path)
    kinds = {classify_license(value).canonical_license for value in licenses}
    mixed_copyleft = "STK-4.3" in kinds and any(
        item in _TRAIN_ONLY for item in kinds
    )
    if "impulse-tests" in path:
        if mixed_copyleft:
            bucket = "faust-impulse-mixed"
        elif canonical == "BSD":
            bucket = "faust-impulse-bsd"
        elif canonical == "STK-4.3":
            bucket = "faust-impulse-stk"
        elif canonical in _TRAIN_ONLY or "LGPL" in canonical.upper() or canonical.startswith("GPL"):
            if path.endswith(("math.lib", "music.lib", "maxmsp.lib")):
                bucket = "faust-impulse-deprecated-libs"
            elif "midi" in path.lower():
                bucket = "faust-gpl-midi-tester"
            elif path.endswith("thru_zero_flanger.dsp"):
                bucket = "faust-gpl-thru-zero-flanger"
            else:
                bucket = "faust-impulse-copyleft"
        else:
            bucket = "faust-impulse-other"
    else:
        if canonical == "BSD":
            bucket = "faust-examples-bsd"
        elif canonical == "MIT":
            bucket = "faust-examples-mit"
        elif canonical == "STK-4.3":
            bucket = "faust-examples-stk"
        elif "midi" in path.lower() and canonical.startswith("GPL"):
            bucket = "faust-gpl-midi-tester"
        else:
            bucket = "faust-examples-other"
    decision = classified.decision
    if decision == "rights_cleared" and not copyright:
        decision = "needs_human"
    return FileVerdict(
        bucket,
        canonical,
        decision,
        "OBSERVED",
        copyright,
        classified.redistribute and "redistribute" in eligible,
        eligible if decision == "rights_cleared" else (),
        False,
        findings,
    )


def _grant_from_comment(block: str) -> tuple[str, str] | None:
    if re.search(r"GRAME LICENSE|GNU Lesser General Public License", block):
        copy = ""
        for line in block.splitlines():
            if re.search(r"Copyright", line):
                copy = line.strip(" /*")
                break
        return "LGPL-2.1-or-later", copy or "GRAME"
    if re.search(r"STK-4\.3", block) and re.search(r"released under", block, re.IGNORECASE):
        copy = ""
        for line in block.splitlines():
            if re.search(r"Copyright", line):
                copy = line.strip(" /*")
                break
        return "STK-4.3", copy
    if re.search(r"released into the public domain|unencumbered software", block, re.IGNORECASE):
        return "Unlicense", "public domain dedication"
    if re.search(r"released under the MIT|MIT License", block):
        return "MIT", ""
    return None


def _headers_by_line(lines: list[str]) -> list[tuple[str, str]]:
    current = ("", "")
    headers: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        block: list[str] = []
        if stripped.startswith("/*"):
            while index < len(lines):
                block.append(lines[index])
                if "*/" in lines[index]:
                    index += 1
                    break
                index += 1
        elif stripped.startswith("//"):
            while index < len(lines) and lines[index].strip().startswith("//"):
                block.append(lines[index])
                index += 1
        else:
            headers.append(current)
            index += 1
            continue
        grant = _grant_from_comment("\n".join(block))
        if grant is not None:
            current = grant
        headers.extend([current] * len(block))
    return headers


def slice_library(text: str, *, reject_whole: bool = False) -> list[FunctionSlice]:
    """Split a faustlibraries file into function metadata.

    Undeclared functions take the section header. With no header they
    are rejected. ``reject_whole`` forces that rejection for mi.lib and
    tubes.lib, whose prose is not a grant.
    """
    stripped = strip_cc_todo(text)
    declares: dict[str, dict[str, str]] = {}
    for item in parse_declares(text):
        if item.owner:
            declares.setdefault(item.owner, {})[item.kind] = item.value
    lines = text.splitlines()
    headers = _headers_by_line(lines)
    slices: list[FunctionSlice] = []
    for match in _FUNC.finditer(text):
        name, _args, rhs = match.group(1), match.group(2), match.group(3)
        if rhs.startswith("library("):
            continue
        line_no = text[: match.start()].count("\n")
        header_license, header_copy = headers[line_no] if line_no < len(headers) else ("", "")
        own = declares.get(name, {})
        if reject_whole:
            license_name, source = "unlicensed", "none"
        elif "license" in own:
            license_name, source = own["license"], "declare"
        elif header_license:
            license_name, source = header_license, "header"
        else:
            license_name, source = "unlicensed", "none"
        classified = classify_license(license_name)
        copyright = own.get("copyright") or own.get("author") or header_copy
        decision = classified.decision
        if decision == "rights_cleared" and not copyright:
            decision = "needs_human"
        start = text.rfind("\n", 0, match.start())
        body = stripped[max(0, start) : match.end()]
        slices.append(
            FunctionSlice(
                name=name,
                line=line_no + 1,
                license=classified.canonical_license,
                copyright=copyright[:500],
                decision=decision,
                eligible_for=classified.eligible_for if decision == "rights_cleared" else (),
                redistribute=classified.redistribute and decision == "rights_cleared",
                source=source,
                stripped_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            )
        )
    return slices
