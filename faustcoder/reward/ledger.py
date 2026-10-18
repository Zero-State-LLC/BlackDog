"""Persistent quarantine queue and A7 tracker for one artifact store.

The production reward path (``run_signal`` when ``reward_graded`` is
set, ``run_signal_suite``, and ``commit_signal_check``) opens this
ledger. The queue is append-only JSONL. ``rates.json`` is rewritten
under a file lock, so two processes on one store cannot drop each
other's windows. Each host still keeps its own ledger.
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from faustcoder.reward.types import QuarantineQueue, UngradedRateTracker
from faustcoder.store import ArtifactStore


class _LockedRateTracker(UngradedRateTracker):
    """Reload the rates file under the ledger lock, then record one sample."""

    def __init__(self, ledger: RewardLedger) -> None:
        super().__init__(on_change=ledger._write_rates)
        self._ledger = ledger

    def observe(self, policy: str, *, ungraded: bool) -> None:
        with self._ledger._locked():
            self._ledger._read_rates()
            super().observe(policy, ungraded=ungraded)


class RewardLedger:
    """Queue and rate tracker rooted at one directory."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.queue = QuarantineQueue(self.directory / "quarantine.jsonl")
        self._rates_path = self.directory / "rates.json"
        self._lock_path = self.directory / "rates.lock"
        self._thread = threading.Lock()
        self.rates = _LockedRateTracker(self)
        with self._locked():
            self._read_rates()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Hold the in-process lock and an exclusive flock on ``rates.lock``."""
        self._thread.acquire()
        fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
            self._thread.release()

    def _read_rates(self) -> None:
        if not self._rates_path.is_file():
            self.rates.load_state(
                {"samples": {}, "alarmed": [], "baseline": self.rates.baseline}
            )
            return
        payload = json.loads(self._rates_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("rates file is not an object")
        self.rates.load_state(payload)

    def _write_rates(self) -> None:
        """Write the tracker. The caller already holds ``_locked``."""
        body = json.dumps(self.rates.export_state(), separators=(",", ":"), sort_keys=True)
        temporary = self._rates_path.with_suffix(".json.tmp")
        fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_CLOEXEC, 0o640)
        try:
            os.fchmod(fd, 0o640)
            os.write(fd, (body + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, self._rates_path)


def ledger_for_store(store: ArtifactStore) -> RewardLedger:
    """Return the ledger that lives beside ``store``."""
    return RewardLedger(store.root / "reward-ledger")
