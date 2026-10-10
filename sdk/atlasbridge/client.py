import json
import os
from collections.abc import Iterator

import httpx

LANGUAGES = {"en": "English", "ha": "Hausa", "ig": "Igbo", "yo": "Yoruba"}
_ALIASES = {v.lower(): k for k, v in LANGUAGES.items()}


def _lang(code: str) -> str:
    code = code.strip().lower()
    code = _ALIASES.get(code, code)
    if code not in LANGUAGES and code != "auto":
        raise ValueError(f"Unsupported language '{code}'. Use one of: {', '.join(LANGUAGES)}")
    return code


class AtlasBridgeError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"[{status_code}] {message}")
        self.status_code = status_code
        self.message = message


class AtlasBridge:
    """Client for an AtlasBridge gateway.

    api_key and base_url default to the ATLASBRIDGE_API_KEY and ATLASBRIDGE_BASE_URL
    environment variables.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: float = 300.0):
        self.api_key = api_key or os.environ.get("ATLASBRIDGE_API_KEY")
        if not self.api_key:
            raise ValueError("Missing API key: pass api_key=... or set ATLASBRIDGE_API_KEY.")
        base = (base_url or os.environ.get("ATLASBRIDGE_BASE_URL") or "").rstrip("/")
        if not base:
            raise ValueError("Missing base_url: pass base_url=... or set ATLASBRIDGE_BASE_URL.")
        if not base.endswith("/v1"):
            base += "/v1"
        self.base_url = base
        from . import __version__

        self._http = httpx.Client(
            base_url=base,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": f"atlasbridge-python/{__version__}"},
        )

    # ---- internals ----
    def _post(self, path: str, payload: dict) -> dict:
        r = self._http.post(path, json=payload)
        return self._json(r)

    @staticmethod
    def _json(r: httpx.Response) -> dict:
        try:
            data = r.json()
        except ValueError:
            raise AtlasBridgeError(r.status_code, r.text[:300])
        if r.status_code >= 400:
            msg = data.get("error", {}).get("message") if isinstance(data, dict) else None
            raise AtlasBridgeError(r.status_code, msg or str(data)[:300])
        return data

    @staticmethod
    def _messages(prompt: str | list[dict], system: str | None) -> list[dict]:
        msgs = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else list(prompt)
        if system:
            msgs = [{"role": "system", "content": system}] + [m for m in msgs if m.get("role") != "system"]
        return msgs

    # ---- public API ----
    def chat(self, prompt: str | list[dict], *, system: str | None = None, temperature: float = 0.1,
             max_tokens: int = 512) -> str:
        """Send a prompt (or a list of OpenAI-style messages) and return the reply text."""
        data = self.chat_raw(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
        return data["choices"][0]["message"]["content"]

    def chat_raw(self, prompt: str | list[dict], *, system: str | None = None, temperature: float = 0.1,
                 max_tokens: int = 512) -> dict:
        """Like chat(), but returns the full OpenAI-format response (usage, detected language...)."""
        return self._post("/chat/completions", {
            "model": "n-atlas", "messages": self._messages(prompt, system),
            "temperature": temperature, "max_tokens": max_tokens,
        })

    def stream(self, prompt: str | list[dict], *, system: str | None = None, temperature: float = 0.1,
               max_tokens: int = 512) -> Iterator[str]:
        """Yield the reply piece by piece as N-ATLaS generates it."""
        payload = {"model": "n-atlas", "messages": self._messages(prompt, system), "stream": True,
                   "temperature": temperature, "max_tokens": max_tokens}
        with self._http.stream("POST", "/chat/completions", json=payload) as r:
            if r.status_code >= 400:
                r.read()
                self._json(r)
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                chunk = json.loads(data)
                if "error" in chunk:
                    raise AtlasBridgeError(chunk["error"].get("code", 502), chunk["error"].get("message", "stream error"))
                for ch in chunk.get("choices", []):
                    piece = ch.get("delta", {}).get("content")
                    if piece:
                        yield piece

    def translate(self, text: str, *, to: str, source: str = "auto") -> str:
        """Translate between English, Hausa, Igbo and Yoruba (codes or names: 'ha' or 'Hausa')."""
        return self._post("/translate", {"text": text, "target": _lang(to), "source": _lang(source)})["translation"]

    def detect_language(self, text: str, *, use_model: bool = False) -> dict:
        """Return {'language': 'ha'|'ig'|'yo'|'en'|'und', 'name': ..., ...}."""
        return self._post("/detect-language", {"text": text, "method": "model" if use_model else "heuristic"})

    def usage(self) -> dict:
        return self._json(self._http.get("/usage"))

    def conversation(self, system: str | None = None) -> "Conversation":
        return Conversation(self, system)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Conversation:
    """Keeps message history so follow-up questions have context."""

    def __init__(self, client: AtlasBridge, system: str | None = None):
        self.client = client
        self.messages: list[dict] = [{"role": "system", "content": system}] if system else []

    def say(self, text: str, **kwargs) -> str:
        self.messages.append({"role": "user", "content": text})
        reply = self.client.chat(self.messages, **kwargs)
        self.messages.append({"role": "assistant", "content": reply})
        return reply
