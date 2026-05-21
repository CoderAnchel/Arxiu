"""Cryptographic primitives: bcrypt password hashing, JWT issue/verify,
password generation, TOTP. Pure functions where possible — no DB or HTTP.
"""
from __future__ import annotations

import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Literal

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import InvalidToken, TokenExpired, TokenScopeInsufficient

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_ctx.verify(plain, hashed)
    except Exception:  # passlib raises on malformed hashes
        return False


# ---------------------------------------------------------------------------
# Password generation
# ---------------------------------------------------------------------------

# Curated alphabet — avoids visually ambiguous characters (0/O, 1/l/I) and shell
# specials. 16 chars from this alphabet → ~95 bits of entropy.
_PW_ALPHABET = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ"      # no I, O
    "abcdefghijkmnopqrstuvwxyz"     # no l
    "23456789"                       # no 0, 1
    "!@#$%&*+="                      # safe symbols
)


def generate_password(length: int = 16) -> str:
    """Cryptographically-strong password for admin distribution. Always contains
    at least one upper, one lower, one digit, one symbol."""
    if length < 12:
        raise ValueError("password length must be >= 12")
    while True:
        pw = "".join(secrets.choice(_PW_ALPHABET) for _ in range(length))
        if (
            any(c.isupper() for c in pw)
            and any(c.islower() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in "!@#$%&*+=" for c in pw)
        ):
            return pw


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

TokenType = Literal["access", "refresh", "password_change"]


@dataclass(frozen=True, slots=True)
class JWTKeys:
    private_pem: str
    public_pem: str


@lru_cache(maxsize=1)
def _jwt_keys() -> JWTKeys:
    settings = get_settings()
    return JWTKeys(
        private_pem=settings.jwt_private_key_path.read_text(),
        public_pem=settings.jwt_public_key_path.read_text(),
    )


@dataclass(frozen=True, slots=True)
class TokenClaims:
    sub: str          # user id as string
    role: str
    typ: TokenType
    jti: str
    exp: int
    fam: str | None   # refresh token family id; None for access tokens

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"sub": self.sub, "role": self.role, "typ": self.typ, "jti": self.jti, "exp": self.exp}
        if self.fam:
            d["fam"] = self.fam
        return d


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_access_token(*, user_id: int, role: str, ttl_seconds: int | None = None) -> tuple[str, TokenClaims]:
    settings = get_settings()
    ttl = ttl_seconds or settings.jwt_access_ttl_seconds
    exp = _now() + timedelta(seconds=ttl)
    claims = TokenClaims(
        sub=str(user_id),
        role=role,
        typ="access",
        jti=str(uuid.uuid4()),
        exp=int(exp.timestamp()),
        fam=None,
    )
    token = jwt.encode(claims.as_dict(), _jwt_keys().private_pem, algorithm=settings.jwt_algorithm)
    return token, claims


def issue_password_change_token(*, user_id: int, role: str, ttl_seconds: int = 300) -> tuple[str, TokenClaims]:
    """Short-scoped token issued when a user must change their password before normal access."""
    settings = get_settings()
    exp = _now() + timedelta(seconds=ttl_seconds)
    claims = TokenClaims(
        sub=str(user_id),
        role=role,
        typ="password_change",
        jti=str(uuid.uuid4()),
        exp=int(exp.timestamp()),
        fam=None,
    )
    token = jwt.encode(claims.as_dict(), _jwt_keys().private_pem, algorithm=settings.jwt_algorithm)
    return token, claims


def issue_refresh_token(*, user_id: int, role: str, family_id: str | None = None) -> tuple[str, TokenClaims]:
    settings = get_settings()
    exp = _now() + timedelta(seconds=settings.jwt_refresh_ttl_seconds)
    claims = TokenClaims(
        sub=str(user_id),
        role=role,
        typ="refresh",
        jti=str(uuid.uuid4()),
        exp=int(exp.timestamp()),
        fam=family_id or str(uuid.uuid4()),
    )
    token = jwt.encode(claims.as_dict(), _jwt_keys().private_pem, algorithm=settings.jwt_algorithm)
    return token, claims


def decode_token(token: str, *, expected_type: TokenType | None = None) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(token, _jwt_keys().public_pem, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        msg = str(exc).lower()
        if "expired" in msg:
            raise TokenExpired() from exc
        raise InvalidToken(str(exc)) from exc

    typ = payload.get("typ")
    if expected_type and typ != expected_type:
        raise TokenScopeInsufficient(f"expected {expected_type} token, got {typ}")

    return TokenClaims(
        sub=str(payload["sub"]),
        role=str(payload["role"]),
        typ=typ,  # type: ignore[arg-type]
        jti=str(payload["jti"]),
        exp=int(payload["exp"]),
        fam=payload.get("fam"),
    )


# ---------------------------------------------------------------------------
# TOTP (admin MFA, optional)
# ---------------------------------------------------------------------------

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def totp_provisioning_uri(secret: str, *, label: str, issuer: str = "Arxiu Institut la Ferreria") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def constant_time_equals(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


# Avoid lint warning about unused import — string is used by alphabet curation tests
__all__ = [
    "constant_time_equals",
    "decode_token",
    "generate_password",
    "generate_totp_secret",
    "hash_password",
    "issue_access_token",
    "issue_password_change_token",
    "issue_refresh_token",
    "string",
    "totp_provisioning_uri",
    "verify_password",
    "verify_totp",
]
