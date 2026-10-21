"""Retrieve only missing inventory-pinned source blobs; never changes rights."""

import argparse
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from faustcoder.acquire import git_blob_sha1
from faustcoder.inventory import parse_corpus
from faustcoder.canonical import content_digest_for

MAX_BYTES = 16 * 1024 * 1024


def pinned_url(unit):
    return f"https://raw.githubusercontent.com/{unit.repo}/{unit.pin}/{quote(unit.path, safe='/')}"


def run(repo, discovery_path, sources_path, missing_path, output):
    corpus = parse_corpus(
        json.loads((repo / "corpus/rights-inventory.v1.json").read_text()),
        json.loads((repo / "corpus/notice-manifest.v1.json").read_text()),
    )
    discovery = json.loads(discovery_path.read_text())
    sources = json.loads(sources_path.read_text())
    missing = sorted(set(json.loads(missing_path.read_text())["missing_blobs"]))
    by_blob = defaultdict(list)
    for u in corpus.units + corpus.comparisons:
        by_blob[u.blob_sha].append(u)
    if set(missing) - set(by_blob):
        raise ValueError("missing blob is not inventory pinned")
    output.mkdir(parents=True, exist_ok=False)
    (output / "blobs").mkdir()
    (output / "receipts").mkdir()

    def fetch(blob):
        attempts = []
        for u in sorted(by_blob[blob], key=lambda x: (x.repo, x.pin, x.path)):
            url = pinned_url(u)
            for attempt in range(2):
                try:
                    with urlopen(
                        Request(
                            url, headers={"User-Agent": "BlackDog-pinned-source-audit"}
                        ),
                        timeout=30,
                    ) as res:
                        raw = res.read(MAX_BYTES + 1)
                    if len(raw) > MAX_BYTES:
                        raise ValueError("source exceeds retrieval bound")
                    actual = git_blob_sha1(raw)
                    if actual != blob:
                        raise ValueError("Git blob hash mismatch: " + actual)
                    target = output / "blobs" / blob
                    target.write_bytes(raw)
                    result = dict(
                        blob_sha=blob,
                        status="pin_verified",
                        url=url,
                        path=str(target.resolve()),
                        bytes=len(raw),
                        attempts=attempts,
                    )
                    break
                except Exception as exc:
                    attempts.append(dict(url=url, attempt=attempt + 1, error=str(exc)))
                    time.sleep(0.1)
            else:
                continue
            break
        else:
            result = dict(blob_sha=blob, status="unavailable", attempts=attempts)
        (output / "receipts" / (blob + ".json")).write_text(
            json.dumps(result, indent=2) + "\n"
        )
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(fetch, missing))
    for row in results:
        if row["status"] == "pin_verified":
            discovery["blob_locations"][row["blob_sha"]] = [row["path"]]
            sources[row["blob_sha"]] = row["path"]
    (output / "discovery.json").write_text(json.dumps(discovery, sort_keys=True) + "\n")
    (output / "sources.json").write_text(json.dumps(sources, sort_keys=True) + "\n")
    report = dict(
        requested=len(missing),
        verified=sum(r["status"] == "pin_verified" for r in results),
        unavailable=[r["blob_sha"] for r in results if r["status"] != "pin_verified"],
        inventory_digest=corpus.inventory_digest,
        notice_digest=corpus.notice_digest,
        input_discovery_digest=content_digest_for(
            json.loads(discovery_path.read_text())
        ),
        production_approved=False,
        receipts=results,
    )
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print({k: v for k, v in report.items() if k != "receipts"})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "discovery", "sources", "missing", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    run(a.repo, a.discovery, a.sources, a.missing, a.output)


if __name__ == "__main__":
    main()
