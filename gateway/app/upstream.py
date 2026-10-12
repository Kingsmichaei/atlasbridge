"""Clients for the N-ATLaS inference servers (OpenAI-compatible), with automatic CPU fallback.

Two backends can be configured:
  * primary  (UPSTREAM_URL):          N-ATLaS fp16 on GPU (Kaggle notebook), fast, not always on
  * fallback (UPSTREAM_FALLBACK_URL): N-ATLaS Q4_K_M GGUF on CPU (llama.cpp), slower, always on
Requests go to the primary while it is healthy and switch to the fallback when it is not.
"""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from .config import settings


class UpstreamError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class Backend:
    name: str          # "gpu" or "cpu-backup"
    url: str
    key: str
    max_tokens_cap: int | None = None

    def headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        return h


def backends() -> list[Backend]:
    out = []
    if settings.upstream_url:
        out.append(Backend("gpu", settings.upstream_url, settings.upstream_key))
    if settings.fallback_url:
        out.append(Backend("cpu-backup", settings.fallback_url, settings.fallback_key, settings.fallback_max_tokens))
    return out


# ---------- health (cached so we don't probe on every request) ----------

_health_cache: dict[str, tuple[float, bool]] = {}
HEALTH_TTL = 20.0


async def _probe(b: Backend, timeout: float = 5.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{b.url}/health", headers=b.headers())
        return r.status_code == 200
    except httpx.HTTPError:
        return False


async def is_healthy(b: Backend, *, fresh: bool = False) -> bool:
    now = time.monotonic()
    cached = _health_cache.get(b.name)
    if not fresh and cached and now - cached[0] < HEALTH_TTL:
        return cached[1]
    ok = await _probe(b)
    _health_cache[b.name] = (now, ok)
    return ok


def _mark_down(b: Backend) -> None:
    _health_cache[b.name] = (time.monotonic(), False)


async def candidates() -> list[Backend]:
    """Backends to try, in order: healthy ones first, then the rest as a last resort."""
    bs = backends()
    if not bs:
        raise UpstreamError(503, "N-ATLaS upstream is not configured (set UPSTREAM_URL and/or UPSTREAM_FALLBACK_URL).")
    healthy = [b for b in bs if await is_healthy(b)]
    return healthy + [b for b in bs if b not in healthy]


def build_payload(body: dict, stream: bool) -> dict:
    """Forward only the parameters N-ATLaS understands, with N-ATLaS-friendly defaults."""
    rp = body.get("repetition_penalty", 1.12)  # model-card recommendation
    payload = {
        "model": settings.upstream_model,
        "messages": body["messages"],
        "stream": stream,
        "temperature": body.get("temperature", 0.1),
        "max_tokens": body.get("max_tokens") or 512,
        "repetition_penalty": rp,   # transformers server
        "repeat_penalty": rp,       # llama.cpp server
    }
    if "top_p" in body:
        payload["top_p"] = body["top_p"]
    return payload


def _for_backend(payload: dict, b: Backend) -> dict:
    if b.max_tokens_cap and payload.get("max_tokens", 0) > b.max_tokens_cap:
        return {**payload, "max_tokens": b.max_tokens_cap}
    return payload


def _retryable(status: int) -> bool:
    return status >= 500 or status in (404, 408, 429)


# ---------- requests ----------

async def complete(payload: dict) -> tuple[dict, str]:
    """Return (OpenAI-format completion, backend name)."""
    if settings.mock_upstream:
        return _mock_completion(payload), "mock"
    last: UpstreamError | None = None
    for b in await candidates():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(settings.upstream_timeout, connect=8.0)) as client:
                r = await client.post(f"{b.url}/v1/chat/completions", headers=b.headers(), json=_for_backend(payload, b))
        except httpx.HTTPError as e:
            _mark_down(b)
            last = UpstreamError(502, f"N-ATLaS {b.name} unreachable: {e.__class__.__name__}")
            continue
        if r.status_code >= 400:
            last = UpstreamError(502 if r.status_code >= 500 else r.status_code,
                                 f"N-ATLaS {b.name} error {r.status_code}: {r.text[:300]}")
            if _retryable(r.status_code):
                _mark_down(b)
                continue
            raise last
        return r.json(), b.name
    raise last or UpstreamError(503, "No N-ATLaS backend available.")


async def stream(payload: dict, used: dict | None = None) -> AsyncIterator[dict]:
    """Yield parsed chunk dicts. Falls back to the next backend if one fails before sending anything.

    `used`, if given, receives {"backend": name} once a backend starts streaming.
    """
    if settings.mock_upstream:
        if used is not None:
            used["backend"] = "mock"
        async for chunk in _mock_stream(payload):
            yield chunk
        return
    last: UpstreamError | None = None
    for b in await candidates():
        started = False
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(settings.upstream_timeout, connect=8.0)) as client:
                async with client.stream("POST", f"{b.url}/v1/chat/completions", headers=b.headers(),
                                         json=_for_backend(payload, b)) as r:
                    if r.status_code >= 400:
                        text = (await r.aread()).decode(errors="replace")
                        last = UpstreamError(502 if r.status_code >= 500 else r.status_code,
                                             f"N-ATLaS {b.name} error {r.status_code}: {text[:300]}")
                        if _retryable(r.status_code):
                            _mark_down(b)
                            continue
                        raise last
                    if used is not None:
                        used["backend"] = b.name
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        started = True
                        yield chunk
                    return
        except httpx.HTTPError as e:
            _mark_down(b)
            last = UpstreamError(502, f"N-ATLaS {b.name} unreachable: {e.__class__.__name__}")
            if started:
                raise last
            continue
    raise last or UpstreamError(503, "No N-ATLaS backend available.")


async def health() -> dict:
    if settings.mock_upstream:
        return {"status": "ok", "mode": "mock", "backend": "mock", "backends": {}}
    bs = backends()
    if not bs:
        return {"status": "not_configured", "backends": {}}
    states = {b.name: await is_healthy(b, fresh=True) for b in bs}
    active = next((b.name for b in bs if states[b.name]), None)
    return {
        "status": "ok" if active else "unreachable",
        "backend": active,
        "backends": {k: ("ok" if v else "down") for k, v in states.items()},
    }


# ---------- mock (no GPU needed) ----------

_MOCK_REPLIES = {
    "ha": "Sannu! Wannan amsa ce ta gwaji daga AtlasBridge (yanayin mock).",
    "ig": "Ndewo! Nke a bụ azịza nnwale sitere na AtlasBridge (ọnọdụ mock).",
    "yo": "Ẹ n lẹ! Èyí jẹ́ ìdáhùn àdánwò láti AtlasBridge (mock mode).",
    "en": "Hello! This is a test reply from AtlasBridge running in mock mode.",
}


def _mock_text(payload: dict) -> str:
    from .language import detect

    last = next((m["content"] for m in reversed(payload["messages"]) if m.get("role") == "user"), "")
    if "[[ECHO]]" in last:
        return last.split("[[ECHO]]", 1)[1].strip()
    lang = detect(last)["language"]
    return _MOCK_REPLIES.get(lang, _MOCK_REPLIES["en"])


def _mock_completion(payload: dict) -> dict:
    text = _mock_text(payload)
    prompt_tokens = sum(len(m.get("content", "").split()) for m in payload["messages"])
    completion_tokens = len(text.split())
    return {
        "id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": settings.upstream_model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
    }


async def _mock_stream(payload: dict) -> AsyncIterator[dict]:
    text = _mock_text(payload)
    base = {"id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}", "object": "chat.completion.chunk", "created": int(time.time()), "model": settings.upstream_model}
    yield {**base, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
    for word in text.split(" "):
        await asyncio.sleep(0.01)
        yield {**base, "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}]}
    yield {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
