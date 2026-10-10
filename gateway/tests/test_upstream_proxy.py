"""Exercise the real proxy path (non-mock) against a fake OpenAI-compatible upstream."""
import json, os, subprocess, sys, time, textwrap

import httpx

FAKE = textwrap.dedent('''
    import json
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    app = FastAPI()
    @app.get("/health")
    def h(): return {"status": "ok"}
    @app.post("/v1/chat/completions")
    async def c(req: Request):
        assert req.headers.get("authorization") == "Bearer up-secret"
        b = await req.json()
        assert b["model"] == "n-atlas" and b["repetition_penalty"] == 1.12
        if b.get("stream"):
            def ev():
                for w in ["Sannu ", "da ", "zuwa"]:
                    yield "data: " + json.dumps({"choices":[{"index":0,"delta":{"content":w},"finish_reason":None}]}) + "\\n\\n"
                yield "data: [DONE]\\n\\n"
            return StreamingResponse(ev(), media_type="text/event-stream")
        return {"id":"x","object":"chat.completion","created":0,"model":"n-atlas",
                "choices":[{"index":0,"message":{"role":"assistant","content":"Sannu da zuwa"},"finish_reason":"stop"}],
                "usage":{"prompt_tokens":10,"completion_tokens":3,"total_tokens":13}}
''')


def test_proxy_roundtrip(tmp_path):
    (tmp_path / "fake_up.py").write_text(FAKE)
    db = tmp_path / "gw.db"
    env = {**os.environ, "MOCK_UPSTREAM": "0", "UPSTREAM_URL": "http://127.0.0.1:8771", "UPSTREAM_KEY": "up-secret",
           "ADMIN_TOKEN": "adm", "DATABASE_URL": f"sqlite:///{db}"}
    up = subprocess.Popen([sys.executable, "-m", "uvicorn", "fake_up:app", "--port", "8771", "--log-level", "warning"], cwd=tmp_path)
    gw = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8772", "--log-level", "warning"],
                          cwd=os.path.dirname(os.path.dirname(__file__)), env=env)
    try:
        for _ in range(100):
            try:
                if httpx.get("http://127.0.0.1:8772/health").json()["upstream"]["status"] == "ok":
                    break
            except Exception:
                pass
            time.sleep(0.1)
        key = httpx.post("http://127.0.0.1:8772/admin/keys", headers={"Authorization": "Bearer adm"}, json={"name": "Proxy Test"}).json()["api_key"]
        h = {"Authorization": f"Bearer {key}"}
        r = httpx.post("http://127.0.0.1:8772/v1/chat/completions", headers=h,
                       json={"messages": [{"role": "user", "content": "Sannu"}]})
        assert r.json()["choices"][0]["message"]["content"] == "Sannu da zuwa"
        with httpx.stream("POST", "http://127.0.0.1:8772/v1/chat/completions", headers=h,
                          json={"stream": True, "messages": [{"role": "user", "content": "Sannu"}]}) as s:
            body = "".join(s.iter_text())
        assert "zuwa" in body and body.strip().endswith("[DONE]")
        rep = httpx.get("http://127.0.0.1:8772/admin/report", headers={"Authorization": "Bearer adm"}).json()
        assert rep["successful_requests"] == 2
    finally:
        gw.terminate(); up.terminate()
