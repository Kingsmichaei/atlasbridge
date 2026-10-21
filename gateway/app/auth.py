"""Developer accounts: signup, login, logout and the session cookie (used by the website).

  GET  /auth/config     {signup_code_required}
  POST /auth/signup     {email, password, name, organisation?, code?}  -> logged in
  POST /auth/login      {email, password}                             -> logged in
  POST /auth/logout
  GET  /auth/me
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from . import security
from .config import settings
from .db import SessionLocal, User, UserSession

router = APIRouter(prefix="/auth", tags=["accounts"])

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _signup_code_required() -> bool:
    return bool(settings.signup_code) and settings.account_signup_require_code


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "organisation": u.organisation,
            "created_at": u.created_at.isoformat(),
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


def require_user(request: Request) -> User:
    """The logged-in user, from the session cookie. Also applies the CSRF check to state changes."""
    security.check_csrf(request)
    token_hash = security.session_token_hash(request.cookies.get(security.SESSION_COOKIE))
    if token_hash:
        with SessionLocal() as s:
            sess = s.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
            if sess and security.aware(sess.expires_at) > datetime.now(timezone.utc):
                user = s.get(User, sess.user_id)
                if user:
                    return user
    raise HTTPException(401, "Not logged in.")


def _start_session(response: Response, request: Request, user_id: int) -> None:
    cookie, token_hash = security.new_session_token()
    now = datetime.now(timezone.utc)
    with SessionLocal() as s:
        # Tidy up this user's expired sessions while we're here.
        s.execute(delete(UserSession).where(UserSession.user_id == user_id, UserSession.expires_at < now))
        s.add(UserSession(user_id=user_id, token_hash=token_hash, expires_at=now + timedelta(days=settings.session_days)))
        s.commit()
    response.set_cookie(security.SESSION_COOKIE, cookie, max_age=settings.session_days * 86400, path="/",
                        httponly=True, samesite="lax", secure=security.cookie_secure(request))


class SignupBody(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=256)
    name: str = Field(min_length=2, max_length=120)
    organisation: str = Field(default="", max_length=200)
    code: str = ""


class LoginBody(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=256)


@router.get("/config")
async def auth_config():
    return {"signup_code_required": _signup_code_required()}


@router.post("/signup")
async def signup(body: SignupBody, request: Request, response: Response):
    security.check_csrf(request)
    security.check_attempts("signup", request)
    if _signup_code_required() and not secrets.compare_digest(body.code.strip(), settings.signup_code):
        raise HTTPException(403, "Invalid invite code.")
    email = body.email.strip().lower()
    if not _EMAIL.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    with SessionLocal() as s:
        if s.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(409, "An account with this email already exists. Log in instead.")
        user = User(email=email, name=body.name.strip(), organisation=body.organisation.strip(),
                    password_hash=security.hash_password(body.password), last_login_at=datetime.now(timezone.utc))
        s.add(user)
        s.commit()
        s.refresh(user)
    _start_session(response, request, user.id)
    return user_out(user)


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response):
    security.check_csrf(request)
    security.check_attempts("login", request)
    email = body.email.strip().lower()
    with SessionLocal() as s:
        user = s.scalar(select(User).where(User.email == email))
        if not security.verify_password(user.password_hash if user else None, body.password):
            raise HTTPException(401, "Incorrect email or password.")
        if security.password_needs_rehash(user.password_hash):
            user.password_hash = security.hash_password(body.password)
        user.last_login_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(user)
    _start_session(response, request, user.id)
    return user_out(user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    security.check_csrf(request)
    token_hash = security.session_token_hash(request.cookies.get(security.SESSION_COOKIE))
    if token_hash:
        with SessionLocal() as s:
            s.execute(delete(UserSession).where(UserSession.token_hash == token_hash))
            s.commit()
    response.delete_cookie(security.SESSION_COOKIE, path="/", httponly=True, samesite="lax",
                           secure=security.cookie_secure(request))
    return {"logged_out": True}


@router.get("/me")
async def me(user: User = Depends(require_user)):
    return user_out(user)
