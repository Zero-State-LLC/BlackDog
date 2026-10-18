"""Pinned blob acquisition. No test opens a network connection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from faustcoder.acquire import (
    MAX_BLOB_BYTES,
    DirectoryFetcher,
    GitFetcher,
    GitHubRawFetcher,
    fetch_verified,
    git_blob_sha1,
    raw_url,
)
from faustcoder.errors import AcquireError


class _Opener:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request: object, timeout: float) -> object:
        self.calls += 1
        raise AssertionError("opener must not be called")


def test_empty_blob_vector() -> None:
    assert git_blob_sha1(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def test_directory_fetcher_reads_the_fixture_tree(tmp_path: Path) -> None:
    data = b"process = 1;\n"
    pin = "a" * 40
    target = tmp_path / "acme" / "widgets" / pin / "osc.dsp"
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    fetcher = DirectoryFetcher(tmp_path)
    assert fetcher.fetch("acme/widgets", pin, "osc.dsp", git_blob_sha1(data)) == data
    assert fetch_verified(fetcher, "acme/widgets", pin, "osc.dsp", git_blob_sha1(data)) == data


def test_directory_fetcher_refuses_traversal(tmp_path: Path) -> None:
    fetcher = DirectoryFetcher(tmp_path)
    pin = "a" * 40
    with pytest.raises(AcquireError):
        fetcher.fetch("acme/widgets", pin, "../secret.dsp", "b" * 40)
    with pytest.raises(AcquireError):
        fetcher.fetch("acme/widgets", pin, "/etc/passwd", "b" * 40)


def test_mutable_ref_and_short_pin_do_not_call_the_opener() -> None:
    opener = _Opener()
    fetcher = GitHubRawFetcher(opener)
    for pin in ("main", "abc", "A" * 40):
        with pytest.raises(AcquireError):
            fetcher.fetch("acme/widgets", pin, "osc.dsp", "b" * 40)
        with pytest.raises(AcquireError):
            raw_url("acme/widgets", pin, "osc.dsp")
    assert opener.calls == 0


def test_raw_url_quotes_the_path_and_refuses_dot_segments() -> None:
    pin = "a" * 40
    url = raw_url("acme/widgets", pin, "dir/a b.dsp")
    assert url == f"https://raw.githubusercontent.com/acme/widgets/{pin}/dir/a%20b.dsp"
    with pytest.raises(AcquireError):
        raw_url("acme/widgets", pin, "dir/../osc.dsp")


def test_blob_mismatch_and_size_cap() -> None:
    pin = "a" * 40

    class _Bytes:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            return b"hello\n"

    with pytest.raises(AcquireError, match="blob_sha"):
        fetch_verified(_Bytes(), "acme/widgets", pin, "osc.dsp", "b" * 40)

    class _Huge:
        def fetch(self, repo: str, pin: str, path: str, blob_sha: str) -> bytes:
            return b"a" * (MAX_BLOB_BYTES + 1)

    with pytest.raises(AcquireError, match="size"):
        fetch_verified(_Huge(), "acme/widgets", pin, "osc.dsp", "b" * 40)


def test_github_redirect_is_refused() -> None:
    from faustcoder.acquire import _NoRedirect

    with pytest.raises(AcquireError, match="redirect"):
        _NoRedirect().redirect_request(None, None, 302, "found", None, "https://example.test")  # type: ignore[arg-type]


def test_git_fetcher_checks_pin_and_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, ["init", "-b", "main"])
    _git(repo, ["config", "user.email", "snapshot@example.com"])
    _git(repo, ["config", "user.name", "snapshot"])
    (repo / "osc.dsp").write_bytes(b"process = 1;\n")
    _git(repo, ["add", "osc.dsp"])
    _git(repo, ["-c", "commit.gpgsign=false", "commit", "-m", "add"])
    pin = _git(repo, ["rev-parse", "HEAD"]).decode().strip()
    blob_sha = _git(repo, ["rev-parse", "HEAD:osc.dsp"]).decode().strip()
    fetcher = GitFetcher({"acme/widgets": repo})
    assert fetcher.fetch("acme/widgets", pin, "osc.dsp", blob_sha) == b"process = 1;\n"
    with pytest.raises(AcquireError):
        fetcher.fetch("acme/widgets", "main", "osc.dsp", blob_sha)
    with pytest.raises(AcquireError, match="blob sha"):
        fetcher.fetch("acme/widgets", pin, "osc.dsp", "b" * 40)


def _git(repo: Path, args: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )
    return completed.stdout
