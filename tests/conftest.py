"""Pytest fixtures for the artifact store."""

from __future__ import annotations

from pathlib import Path

import pytest

from faustcoder import ArtifactStore


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(tmp_path)
