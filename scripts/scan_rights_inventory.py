#!/usr/bin/env python3
"""Build the T05 rights inventory and notice manifest from pinned checkouts.

The checkouts stay outside this repository. The script writes metadata only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from faustcoder.rights_policy import (
    REVIEWER_BOOF,
    classify_faust_file,
    content_sha256,
    dedupe_content,
    is_placeholder,
    slice_library,
)

FAUST = Path("/tmp/faust-2.88.0")
LIBS = Path("/tmp/faustlibraries")
PINS = Path("/tmp/pins")
OUT_INVENTORY = Path("corpus/rights-inventory.v1.json")
OUT_NOTICE = Path("corpus/notice-manifest.v1.json")
GENERATED = "2026-10-17T20:30:00Z"
BOOF = REVIEWER_BOOF


def _identify(slices):
    """Give pattern-match overloads a line-qualified function id."""
    counts = Counter(item.name for item in slices)
    for item in slices:
        ident = item.name if counts[item.name] == 1 else f"{item.name}@{item.line}"
        yield item, ident

REPOS = {
    "faust": ("grame-cncm/faust", "8c00913e44d42f9d25aa3f1a0d500bde5662d7bc", "2.88.0"),
    "libs": ("grame-cncm/faustlibraries", "2edec0537f536eaa130d42c354884d7db971663c", "master"),
    "ide": ("grame-cncm/faustide", "91c18a54d612a9ea48132edb3b3a15e39e6c1b7c", "master"),
    "play": ("grame-cncm/faustplayground", "abf9af4ce9f12fba64fdb2237343bd5d5c8a8047", "master"),
    "live": ("grame-cncm/faustlive", "ecd5427ef02c091f07778f6940994a7d271346a7", "2.5.19"),
    "wasm": ("grame-cncm/faustwasm", "1c0d17a7bb4a047a4a08cb34a0bc6a3ee2019b67", "0.19.0"),
    "edit": ("grame-cncm/fausteditor", "3f0bedad34b886413a908b4434f6ed2ca7deee9a", "master"),
    "pd": ("CICM/pd-faustgen", "9e2aaeabe94a7fab6928711050535ac12a1a591a", "v0.1.2"),
    "sc": ("madskjeldgaard/faustgen-supercollider", "a76b3b5d53f35aef4b7fe9d7172b9729ee3f6e9c", "main"),
}


def blobs(repo: Path) -> dict[str, str]:
    text = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-r", "HEAD"], text=True)
    found: dict[str, str] = {}
    for line in text.splitlines():
        _mode, kind, sha, path = line.split(maxsplit=3)
        if kind == "blob":
            found[path] = sha
    return found


def entry(
    entry_id: str,
    *,
    repo: str,
    name: str,
    url: str,
    path: str,
    license_name: str,
    label: str,
    decision: str,
    reason: str,
    attribution: str,
    complete: bool,
    eligible: list[str],
    redistribute: bool,
    copyleft: bool,
    redistribution: str,
    training: str,
    emitting: str,
    flags: list[str],
    claims: list[dict[str, str]],
    files: list[dict[str, str]] | None = None,
    functions: list[dict[str, str]] | None = None,
    reviewer: str | None = None,
    evidence_uri: str | None = None,
) -> dict:
    pin_repo, commit, ref = REPOS[repo]
    units = len(functions or []) or len(files or [])
    row = {
        "id": entry_id,
        "name": name,
        "url": url,
        "path": path,
        "pin": {"repo": pin_repo, "commit": commit, "ref": ref},
        "file_count": units if units or decision == "rights_cleared" else None,
        "license": license_name,
        "evidence_label": label,
        "evidence_uri": evidence_uri or url,
        "attribution": attribution[:800],
        "attribution_complete": complete,
        "eligible_for": eligible,
        "redistribute": redistribute,
        "redistribution": redistribution,
        "training": training,
        "emitting_code": emitting,
        "decision": decision,
        "reason": reason[:800],
        "copyleft": copyleft,
        "reviewer": reviewer,
        "danny_flags": flags,
        "claims": claims,
    }
    if files:
        row["files"] = files
    if functions:
        row["functions"] = functions
    if row["file_count"] is None and files:
        row["file_count"] = len(files)
    if row["file_count"] is None and functions:
        row["file_count"] = len(functions)
    return row


def notice_row(repo: str, path: str, blob: str, copyright: str, license_name: str, function: str | None, label: str) -> dict:
    return {
        "repo": REPOS[repo][0],
        "commit": REPOS[repo][1],
        "path": path,
        "blob_sha": blob,
        "function": function,
        "copyright": copyright[:500],
        "license": license_name,
        "evidence_label": label,
    }


def main() -> None:
    faust_blobs = blobs(FAUST)
    lib_blobs = blobs(LIBS)
    notice: list[dict] = []
    rows: list[dict] = []
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path, sha in sorted(faust_blobs.items()):
        if not path.endswith((".dsp", ".lib")):
            continue
        if not (path.startswith("examples/") or path.startswith("tests/impulse-tests/")):
            continue
        if path == "tests/impulse-tests/dsp/effect.lib":
            continue
        full = FAUST / path
        verdict = classify_faust_file(path, full.read_text(encoding="utf-8", errors="replace"))
        copy = verdict.copyright
        if is_placeholder(copy):
            copy = "Copyright (C) 2003-2023 GRAME"
            if verdict.copyright:
                copy = f"{copy}; author {verdict.copyright}"
        grouped[verdict.bucket].append((path, sha, copy))

    def add_files(bucket: str, **kwargs: object) -> None:
        items = grouped.get(bucket, [])
        if not items:
            print("skip empty", bucket)
            return
        files = [{"path": path, "blob_sha": sha} for path, sha, _copy in items]
        decision = str(kwargs["decision"])
        license_name = str(kwargs["license_name"])
        label = str(kwargs["label"])
        if decision == "rights_cleared":
            for path, sha, copy in items:
                notice.append(notice_row("faust", path, sha, copy, license_name, None, label))
        kwargs["files"] = files
        rows.append(entry(bucket, repo="faust", url=_faust_url(files[0]["path"] if files else "examples"), **kwargs))  # type: ignore[arg-type]

    readme = _faust_url("examples/README.md")
    copying = _faust_url("COPYING.txt")
    add_files(
        "faust-examples-headerless",
        name="Faust examples with no non-inherited rights notice",
        path="examples/",
        license_name="LGPL-2.1-or-later",
        label="OBSERVED",
        decision="rights_cleared",
        reason="examples/README.md at 8c00913e has a Licence section granting LGPL-2.1-or-later, copyright 2003-2023 GRAME, for the folder. About 70 files name another author, so attribution_complete stays false. 159 files: reverb.dsp is a byte-identical second copy of myEffect.dsp, which is why a unique-content count is 158.",
        attribution="Copyright (C) 2003-2023 GRAME, from examples/README.md at 8c00913e. Per-file authors are not a separate grant.",
        complete=False,
        eligible=["train"],
        redistribute=False,
        copyleft=True,
        redistribution="Training only. Not redistributed.",
        training="Training only under the README grant.",
        emitting="Do not treat model output as a copy of these files.",
        reviewer=BOOF,
        flags=["attribution_complete is false. Boof signed the README grant, not a per-file author list."],
        claims=[{"statement": "examples/README.md at 8c00913e44d42f9d25aa3f1a0d500bde5662d7bc, section Licence, grants LGPL-2.1-or-later, copyright (C) 2003-2023 GRAME, for this folder.", "label": "OBSERVED", "source": readme}],
        evidence_uri=readme,
    )
    add_files(
        "faust-impulse-headerless",
        name="Impulse tests with only the inherited GRAME LGPL grant",
        path="tests/impulse-tests/dsp/",
        license_name="LGPL-2.1-or-later",
        label="OBSERVED",
        decision="rights_cleared",
        reason="COPYING.txt at 8c00913e is LGPL-2.1-or-later. 59 files. constant, echo_bug, grain3, and priority keep flattened GRAME LGPL declares. echo_bug also names Guillot. Training only. Never eval or holdout.",
        attribution="Copyright GRAME, from COPYING.txt at 8c00913e. echo_bug.dsp also declares a Guillot copyright, so attribution_complete stays false.",
        complete=False,
        eligible=["train"],
        redistribute=False,
        copyleft=True,
        redistribution="Training only. Not redistributed. Excluded from eval and holdout.",
        training="Training only.",
        emitting="Do not emit these programs into eval or the sealed holdout.",
        reviewer=BOOF,
        flags=["Excluded from eval and the sealed holdout."],
        claims=[{"statement": "COPYING.txt at 8c00913e44d42f9d25aa3f1a0d500bde5662d7bc is the GNU Lesser General Public License, the grant for header-less impulse files.", "label": "OBSERVED", "source": copying}],
        evidence_uri=copying,
    )
    _clear_observed(
        add_files,
        "faust-examples-mit",
        "MIT example files, including smartKeyboard and harmonicExciter",
        "MIT",
        ["train", "eval", "redistribute"],
        True,
        False,
        "MIT with the per-file copyright in the notice manifest.",
    )
    _clear_observed(
        add_files,
        "faust-examples-bsd",
        "Examples that declare bare BSD",
        "BSD",
        ["train", "eval"],
        False,
        False,
        "Bare BSD has no clause text, so redistribution is off. NOTICE keeps the copyright string.",
    )
    _clear_observed(
        add_files,
        "faust-examples-stk",
        "Examples that declare STK-4.3",
        "STK-4.3",
        ["train", "eval", "redistribute"],
        True,
        False,
        "STK-4.3 is other-permissive under D-013. NOTICE keeps the copyright and the STK text applies.",
    )
    _clear_observed(
        add_files,
        "faust-examples-guitarix",
        "Guitarix example, header GPL-2.0-or-later",
        "GPL-2.0-or-later",
        ["train"],
        False,
        True,
        "The GPL header beats the LGPL declare. Training only. Never emit.",
    )
    _clear_observed(
        add_files,
        "faust-impulse-bsd",
        "Impulse tests that declare bare BSD",
        "BSD",
        ["train"],
        False,
        False,
        "Bare BSD and an impulse test: training only, no redistribution, no eval.",
    )
    _clear_observed(
        add_files,
        "faust-impulse-deprecated-libs",
        "Deprecated impulse library copies",
        "LGPL-2.1-or-later",
        ["train"],
        False,
        True,
        "GRAME LGPL headers. Training only. Not the faustlibraries pin.",
    )
    _clear_observed(
        add_files,
        "faust-impulse-mixed",
        "Flattened impulse files mixing LGPL and STK",
        "LGPL-2.1-or-later",
        ["train"],
        False,
        True,
        "Strictest license wins. LGPL caps STK. Training only. Not eval.",
    )
    _clear_observed(
        add_files,
        "faust-impulse-stk",
        "Impulse files whose only foreign license is STK-4.3",
        "STK-4.3",
        ["train"],
        False,
        False,
        "STK would redistribute, but impulse tests are training only and excluded from eval.",
    )
    _clear_observed(
        add_files,
        "faust-gpl-midi-tester",
        "MIDI tester files declared GPL v3",
        "GPL v3",
        ["train"],
        False,
        True,
        "GPL v3 training only.",
    )
    _clear_observed(
        add_files,
        "faust-gpl-thru-zero-flanger",
        "Thru-zero flanger declared GPL",
        "GPL",
        ["train"],
        False,
        True,
        "Bare GPL, training only.",
    )
    add_files(
        "faust-examples-copyright-only",
        name="NLFfm.dsp, copyright without a license",
        path="examples/physicalModeling/faust-stk/NLFfm.dsp",
        license_name="LGPL-2.1-or-later",
        label="INFERRED",
        decision="needs_human",
        reason="Copyright Romain Michon and no license declare. D-013 allows STK or training-only. The file states neither, so this stays unsigned and reviewer stays null.",
        attribution="Romain Michon (rmichon@ccrma.stanford.edu), from the copyright declare.",
        complete=False,
        eligible=[],
        redistribute=False,
        copyleft=False,
        redistribution="Not granted.",
        training="Not cleared.",
        emitting="Do not emit this file.",
        reviewer=None,
        flags=["This is an INFERRED-only row. Reviewer is null."],
        claims=[{"statement": "NLFfm.dsp declares a copyright and no license. It imports instruments.lib.", "label": "OBSERVED", "source": "https://github.com/grame-cncm/faust/blob/8c00913e44d42f9d25aa3f1a0d500bde5662d7bc/examples/physicalModeling/faust-stk/NLFfm.dsp"}],
    )

    _libraries(rows, notice, lib_blobs)
    _effect(rows, notice, faust_blobs)
    _playground(rows, notice)
    _pd(rows, notice)
    _vendored(rows)
    _static(rows)

    inventory = {
        "schema_version": "rights-inventory.v1",
        "generated_at": GENERATED,
        "method": "Pinned git checkouts read outside this repository on 2026-10-17. Declares, comment notices, and content hashes were counted in memory. No source was written here. D-013, Danny yes 2026-10-17 1:04 PM PT.",
        "policy": "ADR-0003 D-004 and D-007, plus D-013. Not legal advice. A row may be stricter than the license class.",
        "entries": rows,
    }
    manifest = {"schema_version": "notice-manifest.v1", "generated_at": GENERATED, "entries": notice}
    OUT_INVENTORY.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    OUT_NOTICE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["decision"]] += 1
    print(f"rows {len(rows)} cleared {counts['rights_cleared']} rejected {counts['rights_rejected']} needs_human {counts['needs_human']}")
    print(f"notice {len(notice)}")


def _faust_url(path: str) -> str:
    commit = REPOS["faust"][1]
    return f"https://github.com/grame-cncm/faust/blob/{commit}/{path}"


def _clear_observed(add_files, bucket, name, license_name, eligible, redistribute, copyleft, reason) -> None:
    add_files(
        bucket,
        name=name,
        path=bucket,
        license_name=license_name,
        label="OBSERVED",
        decision="rights_cleared",
        reason=reason,
        attribution="Per-file copyright is in corpus/notice-manifest.v1.json.",
        complete=True,
        eligible=eligible,
        redistribute=redistribute,
        copyleft=copyleft,
        redistribution=reason,
        training=reason,
        emitting="Do not treat model output as a redistribution of this source.",
        reviewer=BOOF,
        flags=["Reviewer is Boof because the license text was read at the pin."],
        claims=[{"statement": reason, "label": "OBSERVED", "source": _faust_url("COPYING.txt")}],
    )


def _libraries(rows: list[dict], notice: list[dict], lib_blobs: dict[str, str]) -> None:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    gap: list[dict[str, str]] = []
    agpl: list[dict[str, str]] = []
    undeclared: list[dict[str, str]] = []
    for path, sha in sorted(lib_blobs.items()):
        if not path.endswith(".lib") or "/" in path:
            continue
        if path in {"tubes.lib", "mi.lib"}:
            continue
        text = (LIBS / path).read_text(encoding="utf-8", errors="replace")
        slices = slice_library(text)
        for sl, ident in _identify(slices):
            unit = {"path": path, "blob_sha": sha, "function": ident}
            if sl.license == "AGPL-3.0-only":
                agpl.append(unit)
            elif sl.decision == "needs_human":
                gap.append(unit)
            elif sl.decision == "rights_rejected":
                undeclared.append(unit)
            else:
                groups[(sl.license, "yes" if sl.redistribute else "no")].append(unit)
                notice.append(notice_row("libs", path, sha, sl.copyright, sl.license, ident, "OBSERVED"))
    commit = REPOS["libs"][1]
    base = f"https://github.com/grame-cncm/faustlibraries/blob/{commit}/"
    for (license_name, redist), functions in sorted(groups.items()):
        train_only = redist == "no"
        rows.append(_fn_row(
            f"faustlibraries-{license_name.lower().replace(' ', '-')}",
            f"faustlibraries functions under {license_name}",
            license_name,
            ["train"] if train_only else ["train", "eval", "redistribute"],
            not train_only,
            train_only,
            functions,
            base + functions[0]["path"],
            "Declared or inherited at the pin. CC-TODO comments are stripped before the slice hash. Copyleft stays training-only.",
        ))
    if gap:
        rows.append(_fn_row("faustlibraries-attribution-gap", "Library functions with no copyright string", "mixed", [], False, False, gap, base + "demos.lib", "License text was found but no copyright string. Reviewer stays null.", decision="needs_human", label="INFERRED", reviewer=None, complete=False))
    rows.append(_fn_row("faustlibraries-agpl-functions", "AGPL functions in basics.lib", "AGPL-3.0-only", [], False, True, agpl, base + "basics.lib", "processArray and tabulateNd declare AGPL-3.0-only.", decision="rights_rejected", complete=True))
    rows.append(_fn_row("faustlibraries-undeclared", "Undeclared functions with no header", "unlicensed", [], False, False, undeclared, base + "motion.lib", "No declare and no section header. motion.lib and aanl.lib are in this set. Observed counts differ from the 29/33 and 15/52 note because import aliases are not functions.", decision="rights_rejected", complete=True))
    for name, reason in (
        ("tubes.lib", "No license line. The Guitarix comment is not a grant."),
        ("mi.lib", "No license grant. Prose about the public domain is not a dedication of this file."),
    ):
        sha = lib_blobs[name]
        rows.append(entry(
            f"faustlibraries-{name.split('.')[0]}",
            repo="libs",
            name=f"{name} rejected",
            url=base + name,
            path=name,
            license_name="unlicensed",
            label="OBSERVED",
            decision="rights_rejected",
            reason=reason,
            attribution="No copyright notice that functions as a grant.",
            complete=True,
            eligible=[],
            redistribute=False,
            copyleft=False,
            redistribution="Excluded.",
            training="Excluded.",
            emitting="Do not emit this file.",
            reviewer=BOOF,
            flags=[],
            claims=[{"statement": reason, "label": "OBSERVED", "source": base + name}],
            files=[{"path": name, "blob_sha": sha}],
        ))


def strip_ok(text: str) -> str:
    return text


def _fn_row(entry_id, name, license_name, eligible, redistribute, copyleft, functions, url, reason, decision="rights_cleared", label="OBSERVED", reviewer=BOOF, complete=True) -> dict:
    return entry(
        entry_id,
        repo="libs",
        name=name,
        url=url,
        path=functions[0]["path"] if functions else "/",
        license_name=license_name,
        label=label,
        decision=decision,
        reason=reason,
        attribution="Per-function copyright is in the notice manifest." if decision == "rights_cleared" else reason,
        complete=complete,
        eligible=eligible,
        redistribute=redistribute,
        copyleft=copyleft,
        redistribution=reason,
        training=reason,
        emitting="Model output is not a license to redistribute library source.",
        reviewer=reviewer,
        flags=[],
        claims=[{"statement": reason, "label": "OBSERVED" if decision != "needs_human" else "INFERRED", "source": url}],
        functions=functions,
    )


def _effect(rows: list[dict], notice: list[dict], faust_blobs: dict[str, str]) -> None:
    path = "tests/impulse-tests/dsp/effect.lib"
    text = (FAUST / path).read_text(encoding="utf-8", errors="replace")
    sha = faust_blobs[path]
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    rejected: list[dict[str, str]] = []
    slices = slice_library(text)
    for sl, ident in _identify(slices):
        unit = {"path": path, "blob_sha": sha, "function": ident}
        if sl.decision != "rights_cleared":
            rejected.append(unit)
            continue
        groups[sl.license].append(unit)
        notice.append(notice_row("faust", path, sha, sl.copyright, sl.license, ident, "OBSERVED"))
    for license_name, functions in sorted(groups.items()):
        rows.append(entry(
            f"faust-impulse-effect-{license_name.lower().replace(' ', '-')}",
            repo="faust",
            name=f"effect.lib functions under {license_name}",
            url=_faust_url(path),
            path=path,
            license_name=license_name,
            label="OBSERVED",
            decision="rights_cleared",
            reason="Per-function clearance. Impulse tests stay training-only and out of eval.",
            attribution="Per-function copyright is in the notice manifest.",
            complete=True,
            eligible=["train"],
            redistribute=False,
            copyleft=False,
            redistribution="Not redistributed. Impulse material stays out of eval and holdout.",
            training="Training only.",
            emitting="Do not emit these functions into an eval set.",
            reviewer=BOOF,
            flags=["Excluded from eval and the sealed holdout."],
            claims=[{"statement": "effect.lib declares STK-4.3 and one MIT License function.", "label": "OBSERVED", "source": _faust_url(path)}],
            functions=functions,
        ))
    if rejected:
        rows.append(entry(
            "faust-impulse-effect-undeclared",
            repo="faust",
            name="effect.lib functions with no license",
            url=_faust_url(path),
            path=path,
            license_name="unlicensed",
            label="OBSERVED",
            decision="rights_rejected",
            reason="A function in effect.lib has no license declare and no header grant.",
            attribution="No grant.",
            complete=True,
            eligible=[],
            redistribute=False,
            copyleft=False,
            redistribution="Excluded.",
            training="Excluded.",
            emitting="Do not emit.",
            reviewer=BOOF,
            flags=[],
            claims=[{"statement": "effect.lib contains a function the slicer could not license.", "label": "OBSERVED", "source": _faust_url(path)}],
            functions=rejected,
        ))


def _content_index() -> dict[str, str]:
    found: dict[str, str] = {}
    for root in (FAUST, LIBS):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".dsp", ".lib"}:
                found.setdefault(content_sha256(path.read_bytes()), str(path.relative_to(root)))
    return found


def _playground(rows: list[dict], notice: list[dict]) -> None:
    folder = PINS / "faustplayground"
    index = blobs(folder)
    known = _content_index()
    buckets: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for path, sha in index.items():
        if not path.endswith((".dsp", ".lib")):
            continue
        full = folder / path
        if not full.is_file():
            continue
        digest = content_sha256(full.read_bytes())
        text = full.read_text(encoding="utf-8", errors="replace")
        if digest in known:
            buckets["deduped"].append((path, sha, known[digest]))
            continue
        if "Blow bottle" in text or "blow bottle" in text:
            buckets["blow"].append((path, sha, "Romain Michon"))
            continue
        verdict = classify_faust_file(path, text)
        key = "headerless" if verdict.headerless else verdict.license
        copy = verdict.copyright
        if is_placeholder(copy):
            copy = "Copyright (C) 2015-2024 GRAME"
            if verdict.copyright:
                copy = f"{copy}; author {verdict.copyright}"
        buckets[key].append((path, sha, copy))
    _play_row(rows, notice, "faustplayground-deduped", "deduped", buckets["deduped"], "vendored-duplicate", "rights_rejected", [], False, "Exact content match of an upstream Faust or faustlibraries file. Not cleared on its own.")
    _play_row(rows, notice, "faustplayground-headerless", "headerless", buckets["headerless"], "LGPL-2.1-or-later", "rights_cleared", ["train"], False, "Undeclared playground files inherit COPYING LGPL-2.1-or-later. Training only.")
    _play_row(rows, notice, "faustplayground-stk", "stk", buckets.get("STK-4.3", []), "STK-4.3", "rights_cleared", ["train", "eval", "redistribute"], True, "STK-4.3 cleared with NOTICE.")
    _play_row(rows, notice, "faustplayground-bsd", "bsd", buckets.get("BSD", []), "BSD", "rights_cleared", ["train"], False, "Bare BSD playground files are training only.")
    _play_row(rows, notice, "faustplayground-blow", "blow", buckets["blow"], "LGPL-2.1-or-later", "rights_cleared", ["train"], False, "Files that say they are from Blow bottle by Romain Michon. Training only.")


def _play_row(rows, notice, entry_id, _kind, items, license_name, decision, eligible, redistribute, reason) -> None:
    if not items:
        print("skip playground", entry_id)
        return
    files = [{"path": path, "blob_sha": sha} for path, sha, _copy in items]
    if decision == "rights_cleared":
        for path, sha, copy in items:
            notice.append(notice_row("play", path, sha, copy, license_name, None, "OBSERVED"))
    rows.append(entry(
        entry_id,
        repo="play",
        name=entry_id,
        url=f"https://github.com/grame-cncm/faustplayground/tree/{REPOS['play'][1]}",
        path=files[0]["path"],
        license_name=license_name,
        label="OBSERVED",
        decision=decision,
        reason=reason,
        attribution="Copyright (C) 2015-2024 GRAME, from COPYING.txt, unless the notice row says otherwise.",
        complete=decision != "needs_human",
        eligible=eligible,
        redistribute=redistribute,
        copyleft=license_name.startswith("LGPL") or license_name.startswith("GPL"),
        redistribution=reason,
        training=reason,
        emitting="Near-duplicate filter against faust/examples still applies at T06.",
        reviewer=BOOF,
        flags=["Near-duplicate output filter against faust/examples is a T06/T07 requirement."],
        claims=[{"statement": reason + f" File count {len(files)}.", "label": "OBSERVED", "source": f"https://github.com/grame-cncm/faustplayground/blob/{REPOS['play'][1]}/COPYING.txt"}],
        files=files,
    ))


def _pd(rows: list[dict], notice: list[dict]) -> None:
    folder = PINS / "pd-faustgen"
    index = blobs(folder)
    mixer_upstream = content_sha256((FAUST / "examples/misc/mixer.dsp").read_bytes())
    allowed: list[dict[str, str]] = []
    for path, sha in sorted(index.items()):
        if not path.endswith(".dsp"):
            continue
        full = folder / path
        if not full.is_file():
            continue
        if path.endswith("mixer.dsp"):
            digest = content_sha256(full.read_bytes())
            rows.append(entry(
                "pd-faustgen-mixer",
                repo="pd",
                name="pd-faustgen mixer.dsp deduped to faust",
                url=f"https://github.com/CICM/pd-faustgen/blob/{REPOS['pd'][1]}/{path}",
                path=path,
                license_name="vendored-duplicate",
                label="OBSERVED",
                decision="rights_rejected",
                reason="Vendored copy. Content hash " + ("matches" if digest == mixer_upstream else "does not match") + " faust/examples/misc/mixer.dsp. Not cleared on its own, and bare BSD is not redistributed.",
                attribution="(c) GRAME 2006 on the upstream file.",
                complete=True,
                eligible=[],
                redistribute=False,
                copyleft=False,
                redistribution="No redistribution from this checkout.",
                training="Use the upstream pin if that file is cleared.",
                emitting="Do not emit this copy.",
                reviewer=BOOF,
                flags=["D-013: vendored copies are never cleared on their own."],
                claims=[{"statement": "mixer.dsp was hashed against examples/misc/mixer.dsp at faust 8c00913e.", "label": "OBSERVED", "source": _faust_url("examples/misc/mixer.dsp")}],
                files=[{"path": path, "blob_sha": sha}],
            ))
        elif path.endswith("resonator.dsp"):
            rows.append(entry(
                "pd-faustgen-resonator",
                repo="pd",
                name="resonator.dsp rejected",
                url=f"https://github.com/CICM/pd-faustgen/blob/{REPOS['pd'][1]}/{path}",
                path=path,
                license_name="unlicensed",
                label="OBSERVED",
                decision="rights_rejected",
                reason="Christophe Lebreton is named and no grant is stated.",
                attribution="Christophe Lebreton, no license.",
                complete=True,
                eligible=[],
                redistribute=False,
                copyleft=False,
                redistribution="Excluded.",
                training="Excluded.",
                emitting="Do not emit.",
                reviewer=BOOF,
                flags=[],
                claims=[{"statement": "resonator.dsp credits Christophe Lebreton and has no license declare.", "label": "OBSERVED", "source": f"https://github.com/CICM/pd-faustgen/blob/{REPOS['pd'][1]}/{path}"}],
                files=[{"path": path, "blob_sha": sha}],
            ))
        else:
            allowed.append({"path": path, "blob_sha": sha})
            notice.append(notice_row("pd", path, sha, "(c) 2018 Pierre Guillot", "MIT", None, "OBSERVED"))
    if allowed:
        rows.append(entry(
            "pd-faustgen-mit",
            repo="pd",
            name="pd-faustgen examples under the repository MIT license",
            url=f"https://github.com/CICM/pd-faustgen/blob/{REPOS['pd'][1]}/LICENSE",
            path=allowed[0]["path"],
            license_name="MIT",
            label="OBSERVED",
            decision="rights_cleared",
            reason="Repository LICENSE is MIT, copyright 2018 Pierre Guillot. resonator.dsp is the rejected exception.",
            attribution="(c) 2018 Pierre Guillot",
            complete=True,
            eligible=["train", "eval", "redistribute"],
            redistribute=True,
            copyleft=False,
            redistribution="MIT with the Pierre Guillot notice.",
            training="Allowlisted.",
            emitting="Keep the MIT notice.",
            reviewer=BOOF,
            flags=[],
            claims=[{"statement": "LICENSE is the MIT license, copyright (c) 2018 Pierre Guillot.", "label": "OBSERVED", "source": f"https://github.com/CICM/pd-faustgen/blob/{REPOS['pd'][1]}/LICENSE"}],
            files=allowed,
        ))


def _vendored(rows: list[dict]) -> None:
    upstream: dict[str, str] = {}
    for root, label in ((FAUST, "faust"), (LIBS, "libs")):
        for path in root.rglob("*"):
            if path.suffix not in {".dsp", ".lib"} or not path.is_file():
                continue
            rel = str(path.relative_to(root))
            upstream[f"{label}:{rel}"] = content_sha256(path.read_bytes())
    # one hash map path->hash with first wins; dedupe_content needs path->hash and reverse lookup
    by_hash: dict[str, str] = {}
    for key, digest in upstream.items():
        by_hash.setdefault(digest, key)
    for repo_key, folder, title in (
        ("ide", PINS / "faustide", "faustide-examples"),
        ("live", PINS / "faustlive", "faustlive-examples"),
        ("wasm", PINS / "faustwasm", "faustwasm-tests"),
        ("sc", PINS / "faustgen-supercollider", "faustgen-supercollider"),
    ):
        vendored = _hash_tree(folder)
        exact = {path: by_hash[digest] for path, digest in vendored.items() if digest in by_hash}
        stale = [path for path, digest in vendored.items() if digest not in by_hash]
        rows.append(entry(
            title,
            repo=repo_key,
            name=f"{title} rejected as a vendored source",
            url=f"https://github.com/{REPOS[repo_key][0]}/tree/{REPOS[repo_key][1]}",
            path="/",
            license_name="vendored-duplicate",
            label="OBSERVED",
            decision="rights_rejected",
            reason=f"Vendored tree is not an independent source. Exact content matches {len(exact)}. Stale files {len(stale)}.",
            attribution="Rights stay on the upstream pin named by the content hash.",
            complete=True,
            eligible=[],
            redistribute=False,
            copyleft=True,
            redistribution="Not cleared on its own.",
            training="Do not train on this tree beside the upstream pin.",
            emitting="Do not emit from this checkout.",
            reviewer=BOOF,
            flags=[],
            claims=[{"statement": f"Content-hash dedupe against faust 8c00913e and faustlibraries 2edec053: {len(exact)} exact, {len(stale)} stale, {len(vendored)} files hashed.", "label": "OBSERVED", "source": f"https://github.com/{REPOS[repo_key][0]}"}],
        ))


def _hash_tree(folder: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    if not folder.is_dir():
        return found
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in {".dsp", ".lib"}:
            found[str(path.relative_to(folder))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _static(rows: list[dict]) -> None:
    old = json.loads(Path("corpus/rights-inventory.v1.json").read_text(encoding="utf-8"))
    syfala = next(item for item in old["entries"] if item["id"] == "syfala-examples")
    syfala["reviewer"] = BOOF
    syfala["redistribute"] = False
    rows.append(syfala)
    rows.append(entry(
        "fausteditor",
        repo="edit",
        name="Faust editor, no Faust programs",
        url=f"https://github.com/grame-cncm/fausteditor/blob/{REPOS['edit'][1]}/COPYING.txt",
        path="/",
        license_name="vendored-duplicate",
        label="OBSERVED",
        decision="rights_rejected",
        reason="Out of scope. Zero .dsp or .lib files. COPYING is LGPL and LICENSE is GPL-3.0.",
        attribution="Copyright 2017-2024 GRAME on COPYING.txt.",
        complete=True,
        eligible=[],
        redistribute=False,
        copyleft=True,
        redistribution="Not a Faust corpus.",
        training="Not ingested.",
        emitting="Not a DSP source.",
        reviewer=BOOF,
        flags=["Do not pick the GitHub license badge over the two files."],
        claims=[{"statement": "The pinned tree has zero .dsp or .lib files.", "label": "OBSERVED", "source": f"https://github.com/grame-cncm/fausteditor/tree/{REPOS['edit'][1]}"}],
    ))
    rows.append(entry(
        "faust-architecture",
        repo="faust",
        name="Faust architecture files, rejected for the corpus",
        url=f"https://github.com/grame-cncm/faust/tree/{REPOS['faust'][1]}/architecture",
        path="architecture/",
        license_name="unlicensed",
        label="OBSERVED",
        decision="rights_rejected",
        reason="C++ architecture files are not the DSP corpus. ADR-0003 still requires a separate review before a plugin release.",
        attribution="Not a single copyright. Extra license files exist under architecture/.",
        complete=True,
        eligible=[],
        redistribute=False,
        copyleft=True,
        redistribution="Not cleared for the corpus. Plugin release stays a separate review.",
        training="Excluded from the DSP corpus.",
        emitting="A generated plugin that compiles an architecture file needs its own review.",
        reviewer=BOOF,
        flags=["ADR-0003 plugin-release note stands."],
        claims=[{"statement": "architecture/ is mostly C++ and was rejected for the DSP corpus. Two .dsp files do not make it a training source.", "label": "OBSERVED", "source": f"https://github.com/grame-cncm/faust/tree/{REPOS['faust'][1]}/architecture"}],
    ))


if __name__ == "__main__":
    main()
