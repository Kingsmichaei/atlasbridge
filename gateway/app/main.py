"""AtlasBridge gateway: an OpenAI-compatible API in front of N-ATLaS.

Public API (Bearer <atlasbridge key>):
  GET  /v1/models
  POST /v1/chat/completions     OpenAI format, supports stream=true
  POST /v1/translate            {text, source?, target}
  POST /v1/detect-language      {text, method?: "heuristic"|"model"}
  GET  /v1/usage                your own usage summary

Onboarding:
  POST /v1/signup               {name, email, organisation?, code}  -> new key (beta testers)

Admin (Bearer ADMIN_TOKEN):
  POST /admin/keys              create a key
  GET  /admin/keys              list keys
  POST /admin/keys/{id}/revoke
  GET  /admin/report            validation report (JSON or ?format=csv)
"""

import csv
import hashlib
import io
import json
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from . import language, upstream
from .config import ATTRIBUTION, DEFAULT_SYSTEM_PROMPT, settings
from .db import ApiKey, SessionLocal, UsageLog, init_db

VERSION = "0.1.0"

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AtlasBridge",
    version=VERSION,
    description=(
        "OpenAI-compatible developer gateway for N-ATLaS, Nigeria's multilingual LLM "
        "(English, Hausa, Igbo, Yoruba).\n\n" + ATTRIBUTION
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _attribution_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = "N-ATLaS (Awarri Technologies / FMCIDE)"
    return response


def _error(status: int, message: str, type_: str = "invalid_request_error") -> JSONResponse:
    # Same shape as OpenAI errors so existing SDKs surface the message cleanly.
    return JSONResponse(status_code=status, content={"error": {"message": message, "type": type_, "code": status}})


@app.exception_handler(HTTPException)
async def _http_exc(_: Request, exc: HTTPException):
    return _error(exc.status_code, str(exc.detail))


# ---------------- keys & auth ----------------

def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _new_key() -> str:
    return "ab_" + secrets.token_urlsafe(24)


def _create_key(name: str, email: str = "", organisation: str = "") -> tuple[ApiKey, str]:
    raw = _new_key()
    with SessionLocal() as s:
        k = ApiKey(name=name, email=email, organisation=organisation, prefix=raw[:8], key_hash=_hash(raw))
        s.add(k)
        s.commit()
        s.refresh(k)
    return k, raw


def require_key(request: Request) -> ApiKey:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Missing API key. Send 'Authorization: Bearer <your AtlasBridge key>'.")
    raw = auth.split(" ", 1)[1].strip()
    with SessionLocal() as s:
        k = s.scalar(select(ApiKey).where(ApiKey.key_hash == _hash(raw)))
    if not k or not k.active:
        raise HTTPException(401, "Invalid or revoked API key.")
    _rate_limit(k.id)
    return k


def require_admin(request: Request) -> None:
    if not settings.admin_token:
        raise HTTPException(503, "Admin API disabled (ADMIN_TOKEN not set).")
    if not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {settings.admin_token}"):
        raise HTTPException(401, "Admin token required.")


_hits: dict[int, deque] = defaultdict(deque)


def _rate_limit(key_id: int) -> None:
    now = time.monotonic()
    q = _hits[key_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_minute:
        raise HTTPException(429, f"Rate limit: {settings.rate_limit_per_minute} requests per minute.")
    q.append(now)


# ---------------- logging ----------------

def _preview(text: str) -> str:
    return (text or "")[:300] if settings.log_content else ""


def _log(key: ApiKey | None, request: Request, endpoint: str, status: int, started: float, *, lang: str = "",
         prompt_tokens: int = 0, completion_tokens: int = 0, streamed: bool = False,
         prompt: str = "", reply: str = "", error: str = "") -> None:
    with SessionLocal() as s:
        s.add(UsageLog(
            key_id=key.id if key else None,
            endpoint=endpoint,
            language=lang,
            status_code=status,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            streamed=streamed,
            client=request.headers.get("user-agent", "")[:120],
            prompt_preview=_preview(prompt),
            reply_preview=_preview(reply),
            error=error[:500],
        ))
        s.commit()


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return ""


# ---------------- schemas ----------------

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model: str = "n-atlas"
    messages: list[Message] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    max_tokens: int | None = Field(default=None, ge=1, le=2048)
    repetition_penalty: float | None = Field(default=None, ge=1, le=2)
    # AtlasBridge extension: language N-ATLaS should reply in. "auto" (default) follows the
    # user's latest message when no system prompt is supplied.
    language: Literal["auto", "en", "ha", "ig", "yo"] = "auto"


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    target: Literal["en", "ha", "ig", "yo"]
    source: Literal["en", "ha", "ig", "yo", "auto"] = "auto"


class DetectRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    method: Literal["heuristic", "model"] = "heuristic"


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=200)
    organisation: str = Field(default="", max_length=200)
    code: str


class KeyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = ""
    organisation: str = ""


# ---------------- public endpoints ----------------

_STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
async def playground():
    return FileResponse(_STATIC / "index.html")


@app.get("/api")
async def root():
    return {"name": "AtlasBridge", "version": VERSION, "docs": "/docs", "model": "N-ATLaS", "attribution": ATTRIBUTION}


@app.get("/health")
async def health():
    return {"gateway": "ok", "version": VERSION, "upstream": await upstream.health()}


@app.get("/v1/models")
async def models(key: ApiKey = Depends(require_key)):
    return {"object": "list", "data": [{
        "id": "n-atlas", "object": "model", "owned_by": "awarri",
        "languages": ["en", "ha", "ig", "yo"], "context_length": 8192,
    }]}


def _prepare_messages(messages: list[dict], requested: str) -> tuple[list[dict], str, str | None]:
    """Add the default system prompt and an explicit reply-language instruction.

    N-ATLaS (8B) often answers in the wrong Nigerian language when left to infer it,
    especially when earlier turns used another language. Naming the language in the
    system prompt fixes that. Returns (messages, detected_language, reply_language).
    """
    messages = [dict(m) for m in messages]
    detected = language.detect(_last_user_text(messages))
    has_system = any(m["role"] == "system" for m in messages)

    reply_lang = None
    if requested != "auto":
        reply_lang = requested
        instruction = f"Always reply in {language.NAMES[reply_lang]}."
    elif not has_system and detected["language"] != "und":
        reply_lang = detected["language"]
        name = language.NAMES[reply_lang]
        instruction = (f"The user's latest message is in {name}. Reply only in {name}, even if earlier "
                       f"messages used another language, unless the user explicitly asks for a different language.")
    else:
        instruction = ""

    if not has_system:
        messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}] + messages
    if instruction:
        for m in messages:
            if m["role"] == "system":
                m["content"] = f"{m['content'].rstrip()}\n\n{instruction}"
                break
    return messages, detected["language"], reply_lang


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatRequest, request: Request, key: ApiKey = Depends(require_key)):
    started = time.perf_counter()
    raw = body.model_dump(exclude_none=True)
    messages, lang, reply_lang = _prepare_messages(raw["messages"], body.language)
    raw["messages"] = messages
    user_text = _last_user_text(messages)
    payload = upstream.build_payload(raw, stream=body.stream)

    if not body.stream:
        try:
            result = await upstream.complete(payload)
        except upstream.UpstreamError as e:
            _log(key, request, "chat", e.status_code, started, lang=lang, prompt=user_text, error=e.detail)
            return _error(e.status_code, e.detail, "upstream_error")
        usage = result.get("usage") or {}
        reply = result["choices"][0]["message"]["content"]
        result["model"] = "n-atlas"
        result.setdefault("x_atlasbridge", {}).update(detected_language=lang, reply_language=reply_lang or "unspecified")
        _log(key, request, "chat", 200, started, lang=lang, prompt_tokens=usage.get("prompt_tokens", 0),
             completion_tokens=usage.get("completion_tokens", 0), prompt=user_text, reply=reply)
        return result

    async def events():
        parts: list[str] = []
        status, err = 200, ""
        try:
            async for chunk in upstream.stream(payload):
                chunk["model"] = "n-atlas"
                for ch in chunk.get("choices", []):
                    parts.append(ch.get("delta", {}).get("content") or "")
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except upstream.UpstreamError as e:
            status, err = e.status_code, e.detail
            yield f"data: {json.dumps({'error': {'message': e.detail, 'type': 'upstream_error', 'code': e.status_code}})}\n\n"
        yield "data: [DONE]\n\n"
        reply = "".join(parts)
        _log(key, request, "chat", status, started, lang=lang, completion_tokens=len(reply.split()),
             streamed=True, prompt=user_text, reply=reply, error=err)

    return StreamingResponse(events(), media_type="text/event-stream")


async def _ask(system: str, user: str, max_tokens: int = 512) -> tuple[str, dict]:
    payload = upstream.build_payload(
        {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
         "temperature": 0.1, "max_tokens": max_tokens},
        stream=False,
    )
    result = await upstream.complete(payload)
    return result["choices"][0]["message"]["content"].strip(), result.get("usage") or {}


@app.post("/v1/translate")
async def translate(body: TranslateRequest, request: Request, key: ApiKey = Depends(require_key)):
    started = time.perf_counter()
    source = body.source if body.source != "auto" else language.detect(body.text)["language"]
    if source == "und":
        source = "en"
    if source == body.target:
        return {"translation": body.text, "source": source, "target": body.target, "model": "n-atlas"}
    src_name, tgt_name = language.NAMES[source], language.NAMES[body.target]
    system = (
        f"You are a professional translator. Translate the user's {src_name} text into {tgt_name}. "
        f"Output only the {tgt_name} translation, with no explanations or quotes."
    )
    try:
        text, usage = await _ask(system, body.text, max_tokens=min(1024, 64 + 3 * len(body.text.split())))
    except upstream.UpstreamError as e:
        _log(key, request, "translate", e.status_code, started, lang=body.target, prompt=body.text, error=e.detail)
        return _error(e.status_code, e.detail, "upstream_error")
    _log(key, request, "translate", 200, started, lang=body.target, prompt_tokens=usage.get("prompt_tokens", 0),
         completion_tokens=usage.get("completion_tokens", 0), prompt=body.text, reply=text)
    return {"translation": text, "source": source, "target": body.target, "model": "n-atlas"}


@app.post("/v1/detect-language")
async def detect_language(body: DetectRequest, request: Request, key: ApiKey = Depends(require_key)):
    started = time.perf_counter()
    result = language.detect(body.text)
    result["method"] = "heuristic"
    if body.method == "model":
        system = (
            "Identify the language of the user's text. Answer with exactly one word: "
            "English, Hausa, Igbo, Yoruba, or Other."
        )
        try:
            answer, _ = await _ask(system, body.text, max_tokens=5)
        except upstream.UpstreamError as e:
            _log(key, request, "detect", e.status_code, started, prompt=body.text, error=e.detail)
            return _error(e.status_code, e.detail, "upstream_error")
        word = answer.strip().split()[0].strip(".,:").capitalize() if answer.strip() else "Other"
        by_name = {v: k for k, v in language.NAMES.items()}
        result = {"language": by_name.get(word, "und"), "name": word if word in by_name else "Unknown",
                  "method": "model", "heuristic": result}
    _log(key, request, "detect", 200, started, lang=result["language"], prompt=body.text)
    return result


@app.get("/v1/usage")
async def my_usage(key: ApiKey = Depends(require_key)):
    with SessionLocal() as s:
        rows = s.execute(
            select(UsageLog.endpoint, func.count(), func.avg(UsageLog.latency_ms))
            .where(UsageLog.key_id == key.id).group_by(UsageLog.endpoint)
        ).all()
    return {"key_prefix": key.prefix, "name": key.name,
            "endpoints": [{"endpoint": e, "requests": n, "avg_latency_ms": round(l or 0, 1)} for e, n, l in rows]}


@app.post("/v1/signup")
async def signup(body: SignupRequest, request: Request):
    if not settings.signup_code:
        raise HTTPException(403, "Self-serve signup is closed. Ask the maintainer for a key.")
    if not secrets.compare_digest(body.code.strip(), settings.signup_code):
        raise HTTPException(403, "Invalid invite code.")
    k, raw = _create_key(body.name, body.email, body.organisation)
    return {"api_key": raw, "key_prefix": k.prefix, "name": k.name,
            "note": "Store this key now; it cannot be shown again.",
            "base_url": str(request.base_url).rstrip("/") + "/v1"}


# ---------------- admin ----------------

@app.post("/admin/keys", dependencies=[Depends(require_admin)])
async def admin_create_key(body: KeyCreate):
    k, raw = _create_key(body.name, body.email, body.organisation)
    return {"id": k.id, "api_key": raw, "key_prefix": k.prefix, "name": k.name}


@app.get("/admin/keys", dependencies=[Depends(require_admin)])
async def admin_list_keys():
    with SessionLocal() as s:
        keys = s.scalars(select(ApiKey).order_by(ApiKey.id)).all()
    return [{"id": k.id, "name": k.name, "email": k.email, "organisation": k.organisation,
             "prefix": k.prefix, "active": k.active, "created_at": k.created_at.isoformat()} for k in keys]


@app.post("/admin/keys/{key_id}/revoke", dependencies=[Depends(require_admin)])
async def admin_revoke(key_id: int):
    with SessionLocal() as s:
        k = s.get(ApiKey, key_id)
        if not k:
            raise HTTPException(404, "Key not found.")
        k.active = False
        s.commit()
    return {"id": key_id, "active": False}


@app.get("/admin/report", dependencies=[Depends(require_admin)])
async def admin_report(format: Literal["json", "csv"] = "json"):
    """Validation evidence: per-tester and per-language usage, plus the raw log."""
    with SessionLocal() as s:
        keys = {k.id: k for k in s.scalars(select(ApiKey)).all()}
        logs = s.scalars(select(UsageLog).order_by(UsageLog.created_at)).all()

    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["timestamp_utc", "tester", "organisation", "endpoint", "language", "status", "latency_ms",
                    "prompt_tokens", "completion_tokens", "streamed", "client", "prompt_preview", "reply_preview", "error"])
        for l in logs:
            k = keys.get(l.key_id)
            w.writerow([l.created_at.isoformat(), k.name if k else "", k.organisation if k else "", l.endpoint,
                        l.language, l.status_code, l.latency_ms, l.prompt_tokens, l.completion_tokens, l.streamed,
                        l.client, l.prompt_preview, l.reply_preview, l.error])
        return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=atlasbridge_usage.csv"})

    per_tester: dict = defaultdict(lambda: {"requests": 0, "ok": 0, "languages": defaultdict(int), "endpoints": defaultdict(int),
                                            "first_seen": None, "last_seen": None, "latencies": []})
    per_language: dict = defaultdict(int)
    for l in logs:
        k = keys.get(l.key_id)
        t = per_tester[k.name if k else "unknown"]
        t["requests"] += 1
        t["ok"] += l.status_code == 200
        t["languages"][l.language or "und"] += 1
        t["endpoints"][l.endpoint] += 1
        t["latencies"].append(l.latency_ms)
        ts = l.created_at.isoformat()
        t["first_seen"] = t["first_seen"] or ts
        t["last_seen"] = ts
        per_language[l.language or "und"] += 1

    testers = []
    for name, t in per_tester.items():
        lat = sorted(t.pop("latencies"))
        t["median_latency_ms"] = lat[len(lat) // 2] if lat else 0
        t["success_rate"] = round(t["ok"] / t["requests"], 3) if t["requests"] else 0
        t["languages"], t["endpoints"] = dict(t["languages"]), dict(t["endpoints"])
        testers.append({"tester": name, **t})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_requests": len(logs),
        "successful_requests": sum(1 for l in logs if l.status_code == 200),
        "distinct_testers": len([t for t in testers if t["tester"] != "unknown"]),
        "by_language": dict(per_language),
        "testers": testers,
    }
