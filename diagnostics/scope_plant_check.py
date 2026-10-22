"""Planted-window sensitivity check for an opt-in comparison scope.

AGENT DIAGNOSTIC, NOT FLOOR QUALIFICATION. It plants unlabeled candidate
windows (not gold) into pool hosts and asks, pair by pair, whether the
shipping predicates still join the planted host to the window's comparison
blob with and without a ``ComparisonScope``. Labels, host approval and
fixed-gold freeze remain human gates. Collective support is not exercised
by a single plant and is reported separately by the full recompute.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from faustcoder.neardup import (
    CHAR_MIN_LENGTH, CHAR_NUMERATOR, CHAR_DENOMINATOR, SHORT_SKELETON_NUMERATOR,
    NGRAM_N, SHORT_SKELETON_DENOMINATOR, TOKEN_FLOOR, _canonical_source, _compact, _skeleton,
    char_shingles, containment_at_least, jaccard_at_least, shingles, tokens,
)
from faustcoder.normalize import normalize_bytes


@lru_cache(maxsize=8192)
def _canon(text: str) -> str:
    return _canonical_source(text)


@lru_cache(maxsize=8192)
def stream_tokens(text: str, stream: str) -> tuple[str, ...]:
    return tuple(_canon(text).split()) if stream == "canonical" else tokens(text)


_compact_c = lru_cache(maxsize=8192)(_compact)
_skeleton_c = lru_cache(maxsize=8192)(_skeleton)
_char_c = lru_cache(maxsize=8192)(char_shingles)


@lru_cache(maxsize=8192)
def _sh(text: str, stream: str, n: int = NGRAM_N) -> frozenset[str]:
    return shingles(stream_tokens(text, stream), n)


class DocFreq:
    """Lazy idiom view: a shingle is idiom when its adjusted document frequency >= d."""

    def __init__(self, base: dict[str, Counter], delta: dict[str, Counter], d: int):
        self.base, self.delta, self.d = base, delta, d

    def __getitem__(self, stream: str) -> "_StreamIdiom":
        return _StreamIdiom(self.base[stream], self.delta[stream], self.d)


class _StreamIdiom:
    def __init__(self, base: Counter, delta: Counter, d: int):
        self.base, self.delta, self.d = base, delta, d

    def __contains__(self, s: str) -> bool:
        return self.base.get(s, 0) + self.delta.get(s, 0) >= self.d

    def __rsub__(self, other):
        return frozenset(s for s in other if s not in self)


def pair_joins(part: str, whole: str, idiom, floor: int = TOKEN_FLOOR) -> list[str]:
    """Reasons a cleared ``part`` joins comparison ``whole`` (pairwise, no collective)."""
    reasons = []
    for stream in ("raw", "canonical"):
        p_text = part if stream == "raw" else _canon(part)
        w_text = whole if stream == "raw" else _canon(whole)
        p, w = stream_tokens(part, stream), stream_tokens(whole, stream)
        if p_text == w_text and (stream == "raw" or len(p) < 15 or len(p) >= floor):
            reasons.append(stream + ":exact")
            continue
        sp, sw = _sh(part, stream), _sh(whole, stream)
        if len(p) >= floor and len(w) >= floor and jaccard_at_least(sp, sw):
            reasons.append(stream + ":token_jaccard")
            continue
        if stream == "raw" and not (len(p) >= floor and len(w) >= floor):
            lc, rc = _compact_c(part), _compact_c(whole)
            if part != whole:
                if len(lc) >= CHAR_MIN_LENGTH and len(rc) >= CHAR_MIN_LENGTH:
                    hit = jaccard_at_least(_char_c(part), _char_c(whole), CHAR_NUMERATOR, CHAR_DENOMINATOR)
                else:
                    hit = _skeleton_c(part) == _skeleton_c(whole) and jaccard_at_least(
                        _char_c(part), _char_c(whole), SHORT_SKELETON_NUMERATOR, SHORT_SKELETON_DENOMINATOR)
                if hit:
                    reasons.append("raw:short_character_match")
                    continue
        if idiom is None:
            ssp, ssw = sp, sw
        else:
            i = idiom[stream]
            ssp, ssw = frozenset(x for x in sp if x not in i), frozenset(x for x in sw if x not in i)
        if len(w) >= floor and containment_at_least(ssw, ssp):
            reasons.append(stream + ":reverse_containment")
            continue
        if len(p) < floor:
            continue
        if len(w) >= floor and _sh(part, stream, floor) & _sh(whole, stream, floor):
            reasons.append(stream + ":verbatim_run")
            continue
        if containment_at_least(ssp, ssw):
            reasons.append(stream + ":forward_containment")
    return reasons


def load_pool(recompute: Path):
    index = json.loads((recompute / "source-index.json").read_text())
    ledger = json.loads((recompute / "candidate-ledger.json").read_text())["units"]
    text, repo = {}, {}
    for row in ledger:
        if "selected_source" in row and row.get("normalized_sha256"):
            text[row["unit_id"]] = normalize_bytes((recompute / row["selected_source"]).read_bytes()).text
            repo[row["unit_id"]] = row["repo"]
    comps = {}
    for key, meta in index.items():
        if key.startswith("comparison:"):
            comps[meta["blob_sha"]] = (key, normalize_bytes(Path(meta["source_path"]).read_bytes()).text,
                                       Path(meta["source_path"]))
    return text, repo, comps


def doc_freq(text: dict[str, str]) -> dict[str, Counter]:
    out = {}
    for stream in ("raw", "canonical"):
        c: Counter = Counter()
        for value in text.values():
            c.update(_sh(value, stream))
        out[stream] = c
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recompute", type=Path, required=True, help="a batch1_review output directory")
    ap.add_argument("--windows", type=Path, required=True, help="floor-window-proposals.csv")
    ap.add_argument("--min-docs", type=int, nargs="+", required=True)
    ap.add_argument("--multiplicity", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    text, repo, comps = load_pool(a.recompute)
    base_df = doc_freq(text)
    windows = list(csv.DictReader(a.windows.open()))
    hosts_all = sorted(text)
    rows = []
    for n_done, w in enumerate(windows):
        if n_done % 20 == 0:
            print(f"window {n_done}/{len(windows)}", flush=True)
        _, comp_text, comp_path = comps[w["source_blob"]]
        raw = comp_path.read_bytes()[int(w["start_byte"]):int(w["end_byte"])]
        if hashlib.sha256(raw).hexdigest() != w["window_sha256"]:
            raise ValueError("window hash mismatch: " + w["window_id"])
        win = raw.decode("utf-8")
        order = sorted(hosts_all, key=lambda h: hashlib.sha256((w["window_id"] + h).encode()).hexdigest())
        # Hosts that do not already join this comparison pairwise in either scope.
        free = [h for h in order if not pair_joins(text[h], comp_text, None)][:max(a.multiplicity) * 4]
        for m in a.multiplicity:
            chosen, seen_repo = [], set()
            for h in free:  # prefer distinct repositories, as the FLOOR design requires two
                if repo[h] not in seen_repo or len(seen_repo) >= len(set(repo.values())):
                    chosen.append(h)
                    seen_repo.add(repo[h])
                if len(chosen) == m:
                    break
            planted = {h: normalize_bytes((text[h] + "\n" + win + "\n").encode()).text for h in chosen}
            delta = {s: Counter() for s in base_df}
            for h in chosen:
                for s in delta:
                    delta[s].subtract(_sh(text[h], s))
                    delta[s].update(_sh(planted[h], s))
            for h in chosen:
                rec = dict(window_id=w["window_id"], source_blob=w["source_blob"], raw_tokens=int(w["raw_tokens"]),
                           canonical_tokens=int(w["canonical_tokens"]), multiplicity=m, host=h, host_repo=repo[h],
                           baseline=";".join(pair_joins(planted[h], comp_text, None)))
                for d in a.min_docs:
                    rec[f"scope_df{d}"] = ";".join(pair_joins(planted[h], comp_text, DocFreq(base_df, delta, d)))
                rows.append(rec)
    a.output.mkdir(parents=True, exist_ok=False)
    with (a.output / "plant-results.csv").open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    summary = {}
    for m in a.multiplicity:
        for bucket in (17, 25, 35, 50):
            sel = [r for r in rows if r["multiplicity"] == m and r["raw_tokens"] == bucket]
            ent = {"plants": len(sel), "baseline_detected": sum(bool(r["baseline"]) for r in sel)}
            for d in a.min_docs:
                k = f"scope_df{d}"
                ent[k + "_detected"] = sum(bool(r[k]) for r in sel)
                ent[k + "_lost_vs_baseline"] = sum(bool(r["baseline"]) and not r[k] for r in sel)
            summary[f"m{m}_raw{bucket}"] = ent
    (a.output / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
