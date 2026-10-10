"""Client for the N-ATLaS inference server (OpenAI-compatible), plus a mock for development."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

import httpx

from .config import settings


class UpstreamError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if settings.upstream_key:
        h["Authorization"] = f"Bearer {settings.upstream_key}"
    return h


def build_payload(body: dict, stream: bool) -> dict:
    """Forward only the parameters N-ATLaS understands, with N-ATLaS-friendly defaults."""
    payload = {
        "model": settings.upstream_model,
        "messages": body["messages"],
        "stream": stream,
        "temperature": body.get("temperature", 0.1),
        "max_tokens": body.get("max_tokens") or 512,
        # The model card recommends a repetition penalty of ~1.12.
        "repetition_penalty": body.get("repetition_penalty", 1.12),
    }
    if "top_p" in body:
        payload["top_p"] = body["top_p"]
    return payload


def _check_configured() -> None:
    if not settings.upstream_url:
        raise UpstreamError(503, "N-ATLaS upstream is not configured (UPSTREAM_URL is empty).")


async def complete(payload: dict) -> dict:
    if settings.mock_upstream:
        return _mock_completion(payload)
    _check_configured()
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout) as client:
            r = await client.post(f"{settings.upstream_url}/v1/chat/completions", headers=_headers(), json=payload)
    except httpx.HTTPError as e:
        raise UpstreamError(502, f"N-ATLaS server unreachable: {e.__class__.__name__}") from e
    if r.status_code >= 400:
        raise UpstreamError(502 if r.status_code >= 500 else r.status_code, f"N-ATLaS server error {r.status_code}: {r.text[:300]}")
    return r.json()


async def stream(payload: dict) -> AsyncIterator[dict]:
    """Yield parsed chunk dicts from the upstream SSE stream."""
    if settings.mock_upstream:
        async for chunk in _mock_stream(payload):
            yield chunk
        return
    _check_configured()
    try:
        async with httpx.AsyncClient(timeout=settings.upstream_timeout) as client:
            async with client.stream(
                "POST", f"{settings.upstream_url}/v1/chat/completions", headers=_headers(), json=payload
            ) as r:
                if r.status_code >= 400:
                    text = (await r.aread()).decode(errors="replace")
                    raise UpstreamError(502 if r.status_code >= 500 else r.status_code, f"N-ATLaS server error {r.status_code}: {text[:300]}")
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue
    except httpx.HTTPError as e:
        raise UpstreamError(502, f"N-ATLaS server unreachable: {e.__class__.__name__}") from e


async def health() -> dict:
    if settings.mock_upstream:
        return {"status": "ok", "mode": "mock"}
    if not settings.upstream_url:
        return {"status": "not_configured"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{settings.upstream_url}/health")
        return {"status": "ok" if r.status_code == 200 else f"error {r.status_code}"}
    except httpx.HTTPError as e:
        return {"status": f"unreachable ({e.__class__.__name__})"}


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
    if last.startswith("[[ECHO]]"):
        return last[len("[[ECHO]]"):].strip()
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
