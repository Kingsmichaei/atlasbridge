import os

os.environ["MOCK_UPSTREAM"] = "1"
os.environ["ADMIN_TOKEN"] = "admin-test"
os.environ["SIGNUP_CODE"] = "beta"
os.environ["DATABASE_URL"] = "sqlite:///./test_atlasbridge.db"
os.environ["LOG_CONTENT"] = "1"
if os.path.exists("test_atlasbridge.db"):
    os.remove("test_atlasbridge.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import language

ADMIN = {"Authorization": "Bearer admin-test"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def key(client):
    r = client.post("/v1/signup", json={"name": "Ada Tester", "email": "ada@example.com", "code": "beta"})
    assert r.status_code == 200, r.text
    return r.json()["api_key"]


def auth(k):
    return {"Authorization": f"Bearer {k}"}


def test_health(client):
    r = client.get("/health")
    assert r.json()["upstream"]["mode"] == "mock"
    assert "Awarri" in r.headers["x-powered-by"]


def test_auth_required(client):
    r = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401
    assert "error" in r.json()


def test_bad_signup_code(client):
    r = client.post("/v1/signup", json={"name": "X Y", "email": "x@y.zz", "code": "nope"})
    assert r.status_code == 403


def test_chat(client, key):
    r = client.post("/v1/chat/completions", headers=auth(key),
                    json={"messages": [{"role": "user", "content": "Menene amfanin ruwa ga jikin dan Adam?"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "n-atlas"
    assert body["x_atlasbridge"]["detected_language"] == "ha"
    assert body["choices"][0]["message"]["content"]


def test_chat_stream(client, key):
    with client.stream("POST", "/v1/chat/completions", headers=auth(key),
                       json={"stream": True, "messages": [{"role": "user", "content": "Hello there, how are you?"}]}) as r:
        text = "".join(r.iter_text())
    assert "data: [DONE]" in text
    assert '"content": "mock' in text


def test_openai_sdk_compat(client, key):
    """The official OpenAI SDK works unchanged against the gateway."""
    import threading, time
    import uvicorn
    from openai import OpenAI

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    try:
        sdk = OpenAI(api_key=key, base_url="http://127.0.0.1:8765/v1")
        out = sdk.chat.completions.create(model="n-atlas", messages=[{"role": "user", "content": "Kedu ka ị mere?"}])
        assert out.choices[0].message.content
        stream = sdk.chat.completions.create(model="n-atlas", stream=True,
                                             messages=[{"role": "user", "content": "Bawo ni?"}])
        assert "".join((c.choices[0].delta.content or "") for c in stream if c.choices)
    finally:
        server.should_exit = True


def test_translate(client, key):
    r = client.post("/v1/translate", headers=auth(key), json={"text": "[[ECHO]]Ina kwana", "target": "ha", "source": "en"})
    assert r.status_code == 200
    assert r.json()["translation"] == "Ina kwana"


def test_detect(client, key):
    r = client.post("/v1/detect-language", headers=auth(key), json={"text": "Kedu ihe bụ uru mmiri na-arụ n'ahụ mmadụ?"})
    assert r.json()["language"] == "ig"


@pytest.mark.parametrize("text,lang", [
    ("Menene amfanin ruwa ga jikin dan Adam?", "ha"),
    ("Ina son in ƙara koyon ilimin kwamfuta.", "ha"),
    ("Kedu ihe bụ uru mmiri na-arụ n'ahụ mmadụ?", "ig"),
    ("Biko nyere m aka ịchọta ụlọ akwụkwọ.", "ig"),
    ("Kini anfaani omi fun ara eniyan?", "yo"),
    ("Ẹ jọ̀ọ́, ṣé ẹ lè ràn mí lọ́wọ́?", "yo"),
    ("What is the capital of Nigeria?", "en"),
])
def test_language_heuristic(text, lang):
    assert language.detect(text)["language"] == lang


def test_rate_limit(client):
    r = client.post("/admin/keys", headers=ADMIN, json={"name": "Spammer"})
    k = r.json()["api_key"]
    codes = [client.get("/v1/models", headers=auth(k)).status_code for _ in range(25)]
    assert 429 in codes


def test_report(client, key):
    r = client.get("/admin/report", headers=ADMIN)
    rep = r.json()
    assert rep["total_requests"] >= 4
    assert any(t["tester"] == "Ada Tester" for t in rep["testers"])
    csv_r = client.get("/admin/report?format=csv", headers=ADMIN)
    assert csv_r.text.startswith("timestamp_utc")


def test_revoke(client):
    r = client.post("/admin/keys", headers=ADMIN, json={"name": "Temp"})
    kid, k = r.json()["id"], r.json()["api_key"]
    client.post(f"/admin/keys/{kid}/revoke", headers=ADMIN)
    assert client.get("/v1/models", headers=auth(k)).status_code == 401
