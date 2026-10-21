"""The logged-in developer's API keys and usage (session cookie; see auth.py).

  GET    /account/keys
  POST   /account/keys               {label}  -> raw key, shown once
  POST   /account/keys/{id}/rotate            -> new raw key, old one revoked
  POST   /account/keys/{id}/revoke
  DELETE /account/keys/{id}                   revoke + hide; the row stays for usage history
  GET    /account/usage?days=30
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from . import security
from .auth import require_user
from .config import settings
from .db import ApiKey, SessionLocal, UsageLog, User

router = APIRouter(prefix="/account", tags=["accounts"])


def _iso(dt: datetime | None) -> str | None:
    return security.aware(dt).isoformat() if dt else None


def key_out(k: ApiKey) -> dict:
    # Never include key_hash.
    return {"id": k.id, "label": k.label or k.name, "prefix": k.prefix, "created_at": _iso(k.created_at),
            "last_used_at": _iso(k.last_used_at), "revoked_at": _iso(k.revoked_at), "active": k.active}


def _new_user_key(s, user: User, label: str) -> tuple[ApiKey, str]:
    raw = security.new_key()
    k = ApiKey(name=user.name, email=user.email, organisation=user.organisation, prefix=raw[:8],
               key_hash=security.hash_key(raw), user_id=user.id, label=label)
    s.add(k)
    return k, raw


def _own_key(s, user: User, key_id: int) -> ApiKey:
    """The user's key, or 404 (also for other users' keys, so ids don't leak)."""
    k = s.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id, ApiKey.deleted_at.is_(None)))
    if not k:
        raise HTTPException(404, "Key not found.")
    return k


def _revoke(k: ApiKey) -> None:
    k.active = False
    k.revoked_at = k.revoked_at or datetime.now(timezone.utc)


class KeyBody(BaseModel):
    label: str = Field(default="Default", min_length=1, max_length=60)


@router.get("/keys")
async def list_keys(user: User = Depends(require_user)):
    with SessionLocal() as s:
        keys = s.scalars(select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.deleted_at.is_(None))
                         .order_by(ApiKey.id)).all()
    return {"data": [key_out(k) for k in keys], "max_active_keys": settings.max_keys_per_user}


@router.post("/keys")
async def create_key(body: KeyBody, user: User = Depends(require_user)):
    with SessionLocal() as s:
        active = s.scalar(select(func.count()).select_from(ApiKey).where(
            ApiKey.user_id == user.id, ApiKey.active.is_(True), ApiKey.deleted_at.is_(None)))
        if active >= settings.max_keys_per_user:
            raise HTTPException(409, f"You can have at most {settings.max_keys_per_user} active keys. Revoke one first.")
        k, raw = _new_user_key(s, user, body.label.strip() or "Default")
        s.commit()
        s.refresh(k)
    return {**key_out(k), "api_key": raw, "note": "Store this key now; it cannot be shown again."}


@router.post("/keys/{key_id}/rotate")
async def rotate_key(key_id: int, user: User = Depends(require_user)):
    with SessionLocal() as s:
        old = _own_key(s, user, key_id)
        if not old.active:
            raise HTTPException(409, "This key is revoked. Create a new key instead.")
        _revoke(old)
        k, raw = _new_user_key(s, user, old.label or old.name)
        s.commit()
        s.refresh(k)
    return {**key_out(k), "api_key": raw, "replaces": key_id, "note": "Store this key now; it cannot be shown again."}


@router.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: int, user: User = Depends(require_user)):
    with SessionLocal() as s:
        k = _own_key(s, user, key_id)
        _revoke(k)
        s.commit()
        s.refresh(k)
    return key_out(k)


@router.delete("/keys/{key_id}")
async def delete_key(key_id: int, user: User = Depends(require_user)):
    # Soft delete: usage_logs rows point at the key, so the row stays and its usage still counts.
    with SessionLocal() as s:
        k = _own_key(s, user, key_id)
        _revoke(k)
        k.deleted_at = datetime.now(timezone.utc)
        s.commit()
    return {"id": key_id, "deleted": True}


@router.get("/usage")
async def usage(days: int = Query(30, ge=1, le=365), user: User = Depends(require_user)):
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as s:
        keys = {k.id: k for k in s.scalars(select(ApiKey).where(ApiKey.user_id == user.id)).all()}
        logs = s.scalars(select(UsageLog).where(UsageLog.key_id.in_(keys), UsageLog.created_at >= since)).all() if keys else []

    per_day: dict = defaultdict(lambda: {"requests": 0, "errors": 0})
    for l in logs:
        d = per_day[security.aware(l.created_at).date().isoformat()]
        d["requests"] += 1
        d["errors"] += l.status_code != 200
    by_key = Counter(l.key_id for l in logs)
    ok = sum(1 for l in logs if l.status_code == 200)
    lat = sorted(l.latency_ms for l in logs)
    return {
        "days": days,
        "since": since.isoformat(),
        "totals": {
            "requests": len(logs),
            "successful": ok,
            "success_rate": round(ok / len(logs), 3) if logs else None,
            "median_latency_ms": lat[len(lat) // 2] if lat else None,
            "prompt_tokens": sum(l.prompt_tokens for l in logs),
            "completion_tokens": sum(l.completion_tokens for l in logs),
        },
        "per_day": [{"date": (since + timedelta(days=i)).date().isoformat(),
                     **per_day.get((since + timedelta(days=i)).date().isoformat(), {"requests": 0, "errors": 0})}
                    for i in range(days)],
        "by_endpoint": dict(Counter(l.endpoint for l in logs)),
        "by_language": dict(Counter(l.language or "und" for l in logs)),
        "by_key": [{"id": kid, "label": keys[kid].label or keys[kid].name, "prefix": keys[kid].prefix, "requests": n}
                   for kid, n in by_key.most_common()],
    }
