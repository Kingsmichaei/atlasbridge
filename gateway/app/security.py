"""Shared security helpers: API key hashing, passwords, sessions, CSRF and login rate limits."""

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request

from .config import settings

log = logging.getLogger("atlasbridge")


# ---------------- API keys ----------------

def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_key() -> str:
    return "ab_" + secrets.token_urlsafe(24)


# ---------------- passwords ----------------

_hasher = PasswordHasher()  # argon2id with the library's recommended parameters
# Verified against when the email is unknown, so a login takes as long whether or not the account exists.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Pass None for an unknown email: the dummy hash is still checked, and the result is always False."""
    try:
        ok = _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return ok and password_hash is not None


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# ---------------- client IP and attempt limits ----------------

def client_ip(request: Request) -> str:
    """Best guess at the caller's IP, for rate-limiting logins and signups.

    Never use the first X-Forwarded-For entry: the client can write anything there. Render's
    proxy appends the address it actually saw, so the last entry is the trustworthy one.
    CF-Connecting-IP / True-Client-IP are preferred when present, on the assumption that the edge
    in front of Render (Cloudflare) sets them and overwrites any value the client sent.
    Check the real headers on Render and adjust this function if that assumption doesn't hold.
    """
    for header in ("cf-connecting-ip", "true-client-ip"):
        value = request.headers.get(header, "").strip()
        if value:
            return value
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and forwarded.split(",")[-1].strip():
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


_attempts: dict[tuple[str, str], deque] = defaultdict(deque)
_WINDOW = 15 * 60


def check_attempts(bucket: str, request: Request) -> None:
    """Allow settings.auth_attempts_per_15_min attempts per IP per bucket ("login", "signup")."""
    now = time.monotonic()
    q = _attempts[(bucket, client_ip(request))]
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= settings.auth_attempts_per_15_min:
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
    q.append(now)
    if len(_attempts) > 10_000:  # forget idle IPs so the table can't grow without bound
        for k in [k for k, v in _attempts.items() if not v or now - v[-1] > _WINDOW]:
            del _attempts[k]


# ---------------- sessions ----------------

SESSION_COOKIE = "ab_session"

_secret = settings.session_secret
if not _secret:
    _secret = secrets.token_urlsafe(32)
    log.warning("SESSION_SECRET is not set: using a random one, so dashboard sessions end when the gateway restarts.")


def _sign(token: str) -> str:
    return hmac.new(_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def new_session_token() -> tuple[str, str]:
    """Returns (cookie value, token hash to store). The cookie is token.signature."""
    token = secrets.token_urlsafe(32)
    return f"{token}.{_sign(token)}", hash_key(token)


def session_token_hash(cookie: str | None) -> str | None:
    """The stored hash for a session cookie, or None if it's missing or the signature is wrong."""
    if not cookie or "." not in cookie:
        return None
    token, sig = cookie.rsplit(".", 1)
    if not secrets.compare_digest(sig, _sign(token)):
        return None
    return hash_key(token)


def cookie_secure(request: Request) -> bool:
    return (settings.session_cookie_secure or request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https")


def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything here is stored in UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------- CSRF ----------------

CSRF_HEADER = "x-atlasbridge-client"


def check_csrf(request: Request) -> None:
    """Guard cookie-authenticated state changes against cross-site requests.

    Two checks: the request must carry the X-AtlasBridge-Client header, which the website
    always sends and a plain cross-site form can't; and if the browser sent Origin (or,
    failing that, Referer) it must name this host. The SameSite=Lax cookie is a third layer.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if not request.headers.get(CSRF_HEADER):
        raise HTTPException(403, "Missing X-AtlasBridge-Client header.")
    source = request.headers.get("origin") or request.headers.get("referer")
    if source and (source == "null" or urlparse(source).netloc.lower() != request.headers.get("host", "").lower()):
        raise HTTPException(403, "Cross-site request blocked.")
