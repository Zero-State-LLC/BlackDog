"""Planted-window sensitivity check for an opt-in idiom filter.

AGENT DIAGNOSTIC, NOT FLOOR QUALIFICATION. It plants unlabeled candidate
windows (not gold) into pool hosts and asks, pair by pair, whether the
shipping predicates still join the planted host to the window's comparison
blob with and without an ``IdiomFilter``. Labels, host approval and
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

    def __init__(self, base, delta, d, repo_support, repo_delta, min_repos=2):
        self.base, self.delta, self.d = base, delta, d
        self.repo_support, self.repo_delta, self.min_repos = repo_support, repo_delta, min_repos

    def __getitem__(self, stream: str) -> "_StreamIdiom":
        return _StreamIdiom(self.base[stream], self.delta[stream], self.d,
                            self.repo_support[stream], self.repo_delta[stream], self.min_repos)


class _StreamIdiom:
    def __init__(self, base, delta, d, repo_support, repo_delta, min_repos):
        self.base, self.delta, self.d = base, delta, d
        self.repo_support, self.repo_delta, self.min_repos = repo_support, repo_delta, min_repos

    def __contains__(self, s: str) -> bool:
        return (self.base.get(s, 0) + self.delta.get(s, 0) >= self.d
                and self.repo_support.get(s, 0) + self.repo_delta.get(s, 0) >= self.min_repos)

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



def floor_artifact(host, planted, whole, baseline, floor=TOKEN_FLOOR):
    """A baseline hit caused solely by crossing the floor with pre-existing overlap."""
    if not baseline:
        return False
    for reason in baseline:
        stream, kind = reason.split(":", 1)
        if (kind != "forward_containment" or len(stream_tokens(host, stream)) >= floor
                or len(stream_tokens(planted, stream)) < floor
                or not containment_at_least(_sh(host, stream), _sh(whole, stream))):
            return False
    return True


def boundary_windows(windows):
    """Synthetic token-prefix plants, explicitly distinct from original byte windows."""
    extra = []
    for w in windows:
        sequence = tokens(w["text"])
        if len(sequence) < 50:
            continue
        for width in range(36, 50):
            text = " ".join(sequence[:width])
            extra.append({**w, "window_id": w["window_id"] + f"-token-prefix-{width}",
                          "text": text, "raw_tokens": width,
                          "canonical_tokens": len(stream_tokens(text, "canonical")),
                          "kind": "synthetic_token_prefix", "parent_window_id": w["window_id"],
                          "window_sha256": hashlib.sha256(text.encode()).hexdigest()})
    return extra


def summarize(rows, thresholds):
    """Window counts are unions of changed rows, never sums across multiplicities.

    A window can be lost at one host and gained at another; both sets are explicit.
    Net is gained minus lost. Floor-only hits are excluded from these sets.
    """
    def counts(selected, d):
        lost = [r for r in selected if r["baseline"] and not r[f"scope_df{d}"] and not r["floor_artifact"]]
        gained = [r for r in selected if not r["baseline"] and r[f"scope_df{d}"] and not r["floor_artifact"]]
        artifacts = [r for r in selected if r["floor_artifact"]]
        a, b = sorted({r["window_id"] for r in lost}), sorted({r["window_id"] for r in gained})
        return dict(windows=len({r["window_id"] for r in selected}), rows=len(selected),
                    lost_windows=len(a), gained_windows=len(b), net_windows=len(b)-len(a),
                    lost_window_ids=a, gained_window_ids=b, lost_rows=len(lost), gained_rows=len(gained),
                    floor_artifact_windows=len({r["window_id"] for r in artifacts}),
                    floor_artifact_rows=len(artifacts),
                    floor_artifact_lost_rows=sum(not r[f"scope_df{d}"] for r in artifacts))
    thresholds = sorted(set(thresholds))
    flips = []
    reversals = []
    for r in rows:
        states = [bool(r[f"scope_df{d}"]) for d in thresholds]
        directions = {int(b)-int(a) for a,b in zip(states,states[1:])} - {0}
        if -1 in directions:
            record = dict(window_id=r["window_id"], host=r["host"], multiplicity=r["multiplicity"], states=states)
            flips.append(record)
            if directions == {-1,1}:
                reversals.append(record)
    return dict(thresholds=thresholds, net_definition="gained minus lost; distinct union of changed host rows",
                by_D={str(d): counts(rows,d) for d in thresholds},
                by_D_and_m={f"D{d}_m{m}": counts([r for r in rows if r["multiplicity"]==m],d)
                            for d in thresholds for m in sorted({r["multiplicity"] for r in rows})},
                by_D_m_width={f"D{d}_m{m}_raw{w}": counts([r for r in rows if r["multiplicity"]==m and r["raw_tokens"]==w],d)
                              for d in thresholds for m in sorted({r["multiplicity"] for r in rows})
                              for w in sorted({r["raw_tokens"] for r in rows})},
                nonmonotonic_rows=flips, direction_reversal_rows=reversals)

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recompute", type=Path, required=True, help="a batch1_review output directory")
    ap.add_argument("--windows", type=Path, required=True, help="floor-window-proposals.csv")
    ap.add_argument("--min-docs", type=int, nargs="+", required=True)
    ap.add_argument("--multiplicity", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--min-repos", type=int, default=2)
    ap.add_argument("--boundary", action="store_true", help="add synthetic token-prefix plants at every width 36..49")
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    text, repo, comps = load_pool(a.recompute)
    if a.min_repos < 2:
        raise ValueError("min-repos must be >= 2")
    a.min_docs = sorted(set(a.min_docs))
    base_df = doc_freq(text)
    per_repo = {r: doc_freq({h:t for h,t in text.items() if repo[h]==r}) for r in sorted(set(repo.values()))}
    repo_support = {s: Counter(sh for df in per_repo.values() for sh in df[s]) for s in base_df}
    windows = list(csv.DictReader(a.windows.open()))
    for w in windows:
        _, _, comp_path = comps[w["source_blob"]]
        raw = comp_path.read_bytes()[int(w["start_byte"]):int(w["end_byte"])]
        if hashlib.sha256(raw).hexdigest() != w["window_sha256"]:
            raise ValueError("window hash mismatch: " + w["window_id"])
        w["text"] = raw.decode("utf-8")
        w["kind"] = "original_byte_window"
    if a.boundary:
        windows += boundary_windows(windows)
    hosts_all = sorted(text)
    rows = []
    for n_done, w in enumerate(windows):
        if n_done % 20 == 0:
            print(f"window {n_done}/{len(windows)}", flush=True)
        _, comp_text, _ = comps[w["source_blob"]]
        win = w["text"]
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
            repo_delta = {s: Counter() for s in base_df}
            for r in {repo[h] for h in chosen}:
                for stream in base_df:
                    change = Counter()
                    for h in chosen:
                        if repo[h] == r:
                            change.subtract(_sh(text[h], stream))
                            change.update(_sh(planted[h], stream))
                    for sh, delta_count in change.items():
                        old = per_repo[r][stream].get(sh, 0)
                        repo_delta[stream][sh] += int(old + delta_count > 0) - int(old > 0)
            for h in chosen:
                baseline = pair_joins(planted[h], comp_text, None)
                rec = dict(window_id=w["window_id"], source_blob=w["source_blob"], raw_tokens=int(w["raw_tokens"]),
                           canonical_tokens=int(w["canonical_tokens"]), multiplicity=m, host=h, host_repo=repo[h],
                           baseline=";".join(baseline),
                           floor_artifact=floor_artifact(text[h], planted[h], comp_text, baseline),
                           window_kind=w["kind"], idiom_min_repos=a.min_repos)
                for d in a.min_docs:
                    rec[f"scope_df{d}"] = ";".join(pair_joins(planted[h], comp_text, DocFreq(base_df, delta, d, repo_support, repo_delta, a.min_repos)))
                rows.append(rec)
    a.output.mkdir(parents=True, exist_ok=False)
    with (a.output / "plant-results.csv").open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    summary = summarize(rows, a.min_docs)
    summary["idiom_min_repos"] = a.min_repos
    summary["requested_windows"] = len(windows)
    placed = Counter((r["window_id"], r["multiplicity"]) for r in rows)
    summary["underfilled_placements"] = [
        {"window_id": w["window_id"], "requested_hosts": m, "actual_hosts": placed[w["window_id"], m]}
        for w in windows for m in a.multiplicity if placed[w["window_id"], m] < m]
    summary["unplaced_window_ids"] = sorted({w["window_id"] for w in windows} - {r["window_id"] for r in rows})
    (a.output / "windows.json").write_text(json.dumps(windows, indent=1, sort_keys=True) + "\n")
    (a.output / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
