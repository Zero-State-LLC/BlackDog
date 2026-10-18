"""Persistent quarantine queue and A7 tracker for one artifact store.

The production reward path (``run_signal`` when ``reward_graded`` is
set, and ``commit_signal_check``) opens this ledger. The queue is
append-only JSONL. The rate tracker is rewritten beside it so a new
process sees the same window.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from faustcoder.reward.types import QuarantineQueue, UngradedRateTracker
from faustcoder.store import ArtifactStore


class RewardLedger:
    """Queue and rate tracker rooted at one directory."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.queue = QuarantineQueue(self.directory / "quarantine.jsonl")
        self._rates_path = self.directory / "rates.json"
        self.rates = UngradedRateTracker(on_change=self._save_rates)
        self._load_rates()

    def _load_rates(self) -> None:
        if not self._rates_path.is_file():
            return
        payload = json.loads(self._rates_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("rates file is not an object")
        self.rates.load_state(payload)

    def _save_rates(self) -> None:
        body = json.dumps(self.rates.export_state(), separators=(",", ":"), sort_keys=True)
        temporary = self._rates_path.with_suffix(".json.tmp")
        fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o644)
        try:
            os.write(fd, (body + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, self._rates_path)


def ledger_for_store(store: ArtifactStore) -> RewardLedger:
    """Return the ledger that lives beside ``store``."""
    return RewardLedger(store.root / "reward-ledger")
