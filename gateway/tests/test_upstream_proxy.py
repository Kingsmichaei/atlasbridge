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
                if httpx.get("http://127.0.0.1:8772/health", timeout=httpx.Timeout(5.0, connect=0.5)).json()["upstream"]["status"] == "ok":
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


FAKE_CPU = FAKE.replace('"Sannu da zuwa"', '"Sannu (cpu)"').replace('"Sannu ", "da ", "zuwa"', '"Sannu ", "(cpu)"').replace(
    'assert b["model"] == "n-atlas" and b["repetition_penalty"] == 1.12',
    'assert b["repeat_penalty"] == 1.12 and b["max_tokens"] <= 256')


def _wait(url):
    for _ in range(100):
        try:
            return httpx.get(url, timeout=httpx.Timeout(5.0, connect=0.5)).json()
        except Exception:
            time.sleep(0.1)


def test_cpu_fallback_when_gpu_down(tmp_path):
    (tmp_path / "fake_cpu.py").write_text(FAKE_CPU)
    db = tmp_path / "gw.db"
    env = {**os.environ, "MOCK_UPSTREAM": "0",
           "UPSTREAM_URL": "http://127.0.0.1:8779", "UPSTREAM_KEY": "x",          # nothing listens here: GPU "off"
           "UPSTREAM_FALLBACK_URL": "http://127.0.0.1:8773", "UPSTREAM_FALLBACK_KEY": "up-secret",
           "ADMIN_TOKEN": "adm", "DATABASE_URL": f"sqlite:///{db}"}
    cpu = subprocess.Popen([sys.executable, "-m", "uvicorn", "fake_cpu:app", "--port", "8773", "--log-level", "warning"], cwd=tmp_path)
    gw = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8774", "--log-level", "warning"],
                          cwd=os.path.dirname(os.path.dirname(__file__)), env=env)
    try:
        time.sleep(1.5)
        h = _wait("http://127.0.0.1:8774/health")["upstream"]
        assert h["status"] == "ok" and h["backend"] == "cpu-backup" and h["backends"] == {"gpu": "down", "cpu-backup": "ok"}
        key = httpx.post("http://127.0.0.1:8774/admin/keys", headers={"Authorization": "Bearer adm"}, json={"name": "Fallback"}).json()["api_key"]
        hd = {"Authorization": f"Bearer {key}"}
        r = httpx.post("http://127.0.0.1:8774/v1/chat/completions", headers=hd, timeout=30,
                       json={"max_tokens": 1000, "messages": [{"role": "user", "content": "Sannu"}]}).json()
        assert r["choices"][0]["message"]["content"] == "Sannu (cpu)" and r["x_atlasbridge"]["backend"] == "cpu-backup"
        with httpx.stream("POST", "http://127.0.0.1:8774/v1/chat/completions", headers=hd, timeout=30,
                          json={"stream": True, "messages": [{"role": "user", "content": "Sannu"}]}) as s:
            body = "".join(s.iter_text())
        assert "(cpu)" in body
        t = httpx.post("http://127.0.0.1:8774/v1/translate", headers=hd, timeout=30,
                       json={"text": "Hello", "target": "ha", "source": "en"}).json()
        assert t["backend"] == "cpu-backup"
        rep = httpx.get("http://127.0.0.1:8774/admin/report", headers={"Authorization": "Bearer adm"}).json()
        assert rep["by_backend"].get("cpu-backup") == 3
    finally:
        gw.terminate(); cpu.terminate()


def test_migration_adds_backend_column(tmp_path):
    import sqlite3
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE usage_logs (id INTEGER PRIMARY KEY, endpoint VARCHAR(60))")
    con.commit(); con.close()
    code = ("from app.db import init_db, engine; from sqlalchemy import inspect; init_db();"
            "print(sorted(c['name'] for c in inspect(engine).get_columns('usage_logs')))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.dirname(__file__)), env={**os.environ, "DATABASE_URL": f"sqlite:///{db}"})
    assert "'backend'" in out.stdout, out.stderr
