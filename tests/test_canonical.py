"""Hash determinism and the canonical JSON rules."""

from __future__ import annotations

import hashlib

import pytest

from faustcoder import (
    CanonicalError,
    canonical_bytes,
    content_digest_for,
    digest_hex,
    loads_strict,
)


def test_empty_object_is_pinned() -> None:
    assert canonical_bytes({}) == b"{}"
    assert digest_hex({}) == hashlib.sha256(b"{}").hexdigest()
    assert content_digest_for({}) == "sha256:" + digest_hex({})


def test_key_order_does_not_change_the_digest() -> None:
    left = {"b": 1, "a": {"d": [1, {"z": 1, "y": 2}], "c": 3}}
    right = {"a": {"c": 3, "d": [1, {"y": 2, "z": 1}]}, "b": 1}
    assert canonical_bytes(left) == canonical_bytes(right)
    assert digest_hex(left) == digest_hex(right)
    assert canonical_bytes(left) == b'{"a":{"c":3,"d":[1,{"y":2,"z":1}]},"b":1}'


def test_array_order_is_significant() -> None:
    assert digest_hex({"a": [1, 2]}) != digest_hex({"a": [2, 1]})


def test_no_insignificant_whitespace_and_utf8() -> None:
    encoded = canonical_bytes({"k": "é", "p": "a/b"})
    assert encoded == b'{"k":"\xc3\xa9","p":"a/b"}'
    assert b" " not in encoded
    assert not encoded.endswith(b"\n")


def test_string_whitespace_is_significant() -> None:
    assert canonical_bytes({"a": "x y"}) == b'{"a":"x y"}'


def test_controls_are_escaped_and_solidus_is_not() -> None:
    assert canonical_bytes({"a": "\n"}) == b'{"a":"\\n"}'
    assert canonical_bytes({"a": "/"}) == b'{"a":"/"}'


def test_literals_and_signed_zero() -> None:
    assert canonical_bytes({"a": None, "b": True, "c": False}) == (
        b'{"a":null,"b":true,"c":false}'
    )
    assert canonical_bytes({"n": 0.0}) == b'{"n":0.0}'
    assert canonical_bytes({"n": -0.0}) == b'{"n":-0.0}'
    assert digest_hex({"n": 0.0}) != digest_hex({"n": -0.0})
    assert digest_hex({"n": 1}) != digest_hex({"n": 1.0})


def test_unicode_is_not_normalized() -> None:
    composed = {"k": "é"}
    decomposed = {"k": "e\u0301"}
    assert digest_hex(composed) != digest_hex(decomposed)


def test_repeated_calls_match() -> None:
    payload = {"n": 7, "s": "faust"}
    assert digest_hex(payload) == digest_hex(payload)
    assert canonical_bytes(payload) == canonical_bytes(payload)


def test_rejects_non_json_values() -> None:
    with pytest.raises(CanonicalError):
        canonical_bytes({"n": float("nan")})
    with pytest.raises(CanonicalError):
        canonical_bytes({"n": float("inf")})
    with pytest.raises(CanonicalError):
        canonical_bytes({"t": (1, 2)})
    with pytest.raises(CanonicalError):
        canonical_bytes({1: "a"})
    with pytest.raises(CanonicalError):
        canonical_bytes(b"nope")


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(CanonicalError, match="duplicate key"):
        loads_strict('{"a": 1, "a": 2}')
