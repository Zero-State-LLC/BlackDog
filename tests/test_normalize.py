"""Normalization is a pure function of the fetched bytes."""

from __future__ import annotations

from faustcoder.canonical import sha256_prefixed
from faustcoder.errors import NormalizeError
from faustcoder.normalize import LineSlice, NormalizedFile, NormalizedText, combine_files, normalize_bytes


def test_crlf_and_trailing_space_and_tab() -> None:
    raw = b"a \r\nb\t\r\n"
    result = normalize_bytes(raw)
    assert result.text == "a\nb\n"
    assert result.original_sha256 == sha256_prefixed(raw)
    assert result.normalized_sha256 == sha256_prefixed(b"a\nb\n")


def test_no_final_newline_stays_without_one() -> None:
    assert normalize_bytes(b"a \r\nb\t").text == "a\nb"


def test_utf8_bom_is_stripped_from_text_and_kept_in_the_original_digest() -> None:
    raw = b"\xef\xbb\xbfprocess = 1;\n"
    result = normalize_bytes(raw)
    assert result.text == "process = 1;\n"
    assert result.original_sha256 == sha256_prefixed(raw)
    assert result.original_sha256 != result.normalized_sha256


def test_utf16_bom_nul_invalid_and_empty_are_diagnostics() -> None:
    cases = {
        b"\xff\xfeprocess": "utf-16-bom",
        b"\xfe\xffprocess": "utf-16-bom",
        b"a\x00b": "nul-byte",
        b"\xff": "invalid-utf8",
        b" \t\r\n": "empty",
    }
    for raw, reason in cases.items():
        try:
            normalize_bytes(raw)
        except NormalizeError as exc:
            assert exc.reason == reason
        else:
            raise AssertionError(reason)


def test_slice_is_applied_before_trailing_whitespace_is_stripped() -> None:
    raw = b"keep\n drop \nkeep\n"
    result = normalize_bytes(raw, LineSlice("osc", 2, 2))
    assert result.text == "drop"


def test_slice_errors() -> None:
    raw = b"a\n\n"
    try:
        normalize_bytes(raw, LineSlice("osc", 1, 4))
    except NormalizeError as exc:
        assert exc.reason == "slice-out-of-range"
    else:
        raise AssertionError("range")
    try:
        normalize_bytes(raw, LineSlice("osc", 2, 2))
    except NormalizeError as exc:
        assert exc.reason == "slice-empty"
    else:
        raise AssertionError("empty")


def test_no_unicode_normalization() -> None:
    composed = "caf\u00e9\n".encode()
    decomposed = "cafe\u0301\n".encode()
    left = normalize_bytes(composed)
    right = normalize_bytes(decomposed)
    assert left.text != right.text
    assert left.normalized_sha256 != right.normalized_sha256


def test_single_file_group_keeps_that_files_digests() -> None:
    text = normalize_bytes(b"process = 1;\n")
    group = combine_files(
        [NormalizedFile("primary", "osc.dsp", "a" * 40, text)]
    )
    assert group.text == text.text
    assert group.original_sha256 == text.original_sha256
    assert group.normalized_sha256 == text.normalized_sha256


def test_multi_file_group_hashes_the_member_list_and_keeps_primary_first() -> None:
    primary = NormalizedText("import(\"a.lib\");\nprocess = 1;", "sha256:" + "1" * 64, "sha256:" + "2" * 64)
    imported = NormalizedText("x = 1;", "sha256:" + "3" * 64, "sha256:" + "4" * 64)
    group = combine_files(
        [
            NormalizedFile("import", "a.lib", "b" * 40, imported),
            NormalizedFile("primary", "z.dsp", "c" * 40, primary),
        ]
    )
    assert group.files[0].role == "primary"
    assert group.text == "import(\"a.lib\");\nprocess = 1;\nx = 1;"
    assert group.normalized_sha256 != primary.normalized_sha256
    assert group.original_sha256 != primary.original_sha256
    again = combine_files(list(reversed(group.files)))
    assert again.normalized_sha256 == group.normalized_sha256
