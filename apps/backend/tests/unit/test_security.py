"""Unit tests for app.core.security — pure functions, no DB."""
from __future__ import annotations

import pytest

from app.core import security
from app.core.exceptions import InvalidToken, TokenScopeInsufficient


# --- Password hashing -------------------------------------------------------

def test_hash_then_verify_succeeds() -> None:
    h = security.hash_password("correct horse battery staple")
    assert security.verify_password("correct horse battery staple", h)


def test_verify_rejects_wrong_password() -> None:
    h = security.hash_password("right")
    assert not security.verify_password("wrong", h)


def test_verify_swallows_malformed_hash() -> None:
    assert not security.verify_password("anything", "not-a-bcrypt-hash")


def test_two_hashes_of_same_password_differ() -> None:
    a = security.hash_password("same")
    b = security.hash_password("same")
    assert a != b
    assert security.verify_password("same", a)
    assert security.verify_password("same", b)


# --- Password generation ----------------------------------------------------

def test_generate_password_default_length_is_16() -> None:
    pw = security.generate_password()
    assert len(pw) == 16


def test_generated_password_has_all_classes() -> None:
    for _ in range(50):
        pw = security.generate_password()
        assert any(c.isupper() for c in pw)
        assert any(c.islower() for c in pw)
        assert any(c.isdigit() for c in pw)
        assert any(c in "!@#$%&*+=" for c in pw)


def test_generated_password_avoids_ambiguous_chars() -> None:
    forbidden = set("0O1Il")
    for _ in range(50):
        pw = security.generate_password()
        assert not (set(pw) & forbidden)


def test_generated_passwords_are_unique() -> None:
    seen = {security.generate_password() for _ in range(100)}
    assert len(seen) == 100


def test_generate_password_rejects_short_length() -> None:
    with pytest.raises(ValueError):
        security.generate_password(length=8)


# --- JWT round-trip ---------------------------------------------------------

def test_access_token_round_trip() -> None:
    token, claims = security.issue_access_token(user_id=42, role="admin")
    decoded = security.decode_token(token, expected_type="access")
    assert decoded.sub == "42"
    assert decoded.role == "admin"
    assert decoded.typ == "access"
    assert decoded.jti == claims.jti


def test_refresh_token_includes_family() -> None:
    token, claims = security.issue_refresh_token(user_id=1, role="professor")
    decoded = security.decode_token(token, expected_type="refresh")
    assert decoded.fam == claims.fam
    assert decoded.fam is not None


def test_password_change_token_has_correct_scope() -> None:
    token, _ = security.issue_password_change_token(user_id=1, role="professor")
    decoded = security.decode_token(token, expected_type="password_change")
    assert decoded.typ == "password_change"


def test_decode_rejects_wrong_scope() -> None:
    token, _ = security.issue_access_token(user_id=1, role="admin")
    with pytest.raises(TokenScopeInsufficient):
        security.decode_token(token, expected_type="refresh")


def test_decode_rejects_garbage() -> None:
    with pytest.raises(InvalidToken):
        security.decode_token("not-a-jwt")


# --- TOTP -------------------------------------------------------------------

def test_totp_round_trip() -> None:
    secret = security.generate_totp_secret()
    import pyotp
    code = pyotp.TOTP(secret).now()
    assert security.verify_totp(secret, code)


def test_totp_rejects_bad_code() -> None:
    secret = security.generate_totp_secret()
    assert not security.verify_totp(secret, "000000")


def test_totp_handles_empty_inputs() -> None:
    assert not security.verify_totp("", "123456")
    assert not security.verify_totp("ABCDEFGHIJKLMNOP", "")
