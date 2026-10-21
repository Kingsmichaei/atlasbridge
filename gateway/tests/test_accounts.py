"""Developer accounts: signup/login, key management, usage, isolation, CSRF and the v2.2.0 migration."""
import os
import subprocess
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from app import security
from app.main import app

WEB = {"X-AtlasBridge-Client": "web"}
ADMIN = {"Authorization": "Bearer admin-test"}
CHAT = {"messages": [{"role": "user", "content": "Sannu"}]}


@pytest.fixture(scope="module", autouse=True)
def _lifespan():
    with TestClient(app):  # runs init_db once for the module
        yield


@pytest.fixture(autouse=True)
def _reset_attempts():
    security._attempts.clear()


def browser() -> TestClient:
    return TestClient(app, headers=WEB)


def signup(email: str | None = None, password: str = "correct horse", **extra):
    c = browser()
    email = email or f"dev-{uuid.uuid4().hex[:8]}@example.com"
    r = c.post("/auth/signup", json={"email": email, "password": password, "name": "Dev User", "code": "beta", **extra})
    assert r.status_code == 200, r.text
    return c, email


def bearer(k: str) -> dict:
    return {"Authorization": f"Bearer {k}"}


def new_key(c: TestClient, label: str = "Test") -> dict:
    r = c.post("/account/keys", json={"label": label})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- signup / login ----------------

def test_signup_login_logout():
    c, email = signup()
    cookie = c.cookies.get(security.SESSION_COOKIE)
    assert cookie
    me = c.get("/auth/me").json()
    assert me["email"] == email and "password_hash" not in me

    r = c.post("/auth/logout")
    assert r.status_code == 200
    assert c.get("/auth/me").status_code == 401
    # The old cookie is dead server-side, even if a browser kept it.
    stale = browser()
    stale.cookies.set(security.SESSION_COOKIE, cookie)
    assert stale.get("/auth/me").status_code == 401

    r = c.post("/auth/login", json={"email": email.upper(), "password": "correct horse"})
    assert r.status_code == 200, r.text
    assert c.get("/auth/me").json()["last_login_at"]


def test_session_cookie_flags():
    c = browser()
    r = c.post("/auth/signup", json={"email": f"f-{uuid.uuid4().hex[:6]}@example.com", "password": "12345678",
                                     "name": "Flag Check", "code": "beta"})
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc and "secure" not in sc  # plain http in tests
    r = c.post("/auth/login", headers={"X-Forwarded-Proto": "https"},
               json={"email": c.get("/auth/me").json()["email"], "password": "12345678"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_tampered_cookie_rejected():
    c, _ = signup()
    token = c.cookies.get(security.SESSION_COOKIE)
    other = browser()
    other.cookies.set(security.SESSION_COOKIE, token[:-1] + ("0" if token[-1] != "0" else "1"))
    assert other.get("/auth/me").status_code == 401


def test_wrong_password_rejected():
    _, email = signup()
    c = browser()
    r = c.post("/auth/login", json={"email": email, "password": "wrong password"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "Incorrect email or password."
    r = c.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "Incorrect email or password."
    assert c.get("/auth/me").status_code == 401


def test_duplicate_email():
    _, email = signup()
    r = browser().post("/auth/signup", json={"email": email.upper(), "password": "another-pass", "name": "Dup", "code": "beta"})
    assert r.status_code == 409


def test_signup_validation_and_code():
    c = browser()
    assert c.get("/auth/config").json() == {"signup_code_required": True}
    base = {"email": f"v-{uuid.uuid4().hex[:6]}@example.com", "password": "12345678", "name": "Val Idate"}
    assert c.post("/auth/signup", json={**base, "code": "nope"}).status_code == 403
    assert c.post("/auth/signup", json=base).status_code == 403
    r = c.post("/auth/signup", json={**base, "password": "short", "code": "beta"})
    assert r.status_code == 422 and "password" in r.json()["error"]["message"]
    assert c.post("/auth/signup", json={**base, "email": "not-an-email", "code": "beta"}).status_code == 422


def test_old_endpoints_keep_default_validation_shape():
    r = TestClient(app).post("/v1/signup", json={"name": "x"})
    assert r.status_code == 422 and "detail" in r.json()


def test_login_rate_limited_per_ip():
    c = browser()
    codes = [c.post("/auth/login", json={"email": "x@example.com", "password": "bad-pass"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[10:] == [429, 429]
    # A different client IP (last X-Forwarded-For hop) has its own allowance.
    r = c.post("/auth/login", headers={"X-Forwarded-For": "203.0.113.9, 198.51.100.7"},
               json={"email": "x@example.com", "password": "bad-pass"})
    assert r.status_code == 401


def test_client_ip_lookup():
    from starlette.requests import Request

    def req(headers):
        return Request({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
                        "client": ("10.0.0.1", 1234)})
    assert security.client_ip(req({})) == "10.0.0.1"
    assert security.client_ip(req({"x-forwarded-for": "1.1.1.1, 2.2.2.2"})) == "2.2.2.2"  # spoofable first hop ignored
    assert security.client_ip(req({"x-forwarded-for": "1.1.1.1", "true-client-ip": "3.3.3.3"})) == "3.3.3.3"
    assert security.client_ip(req({"true-client-ip": "3.3.3.3", "cf-connecting-ip": "4.4.4.4"})) == "4.4.4.4"


# ---------------- CSRF and auth required ----------------

def test_account_routes_need_session():
    c = browser()
    for method, path in [("get", "/account/keys"), ("post", "/account/keys"), ("get", "/account/usage"),
                         ("post", "/account/keys/1/rotate"), ("post", "/account/keys/1/revoke"),
                         ("delete", "/account/keys/1"), ("get", "/auth/me")]:
        r = getattr(c, method)(path)
        assert r.status_code == 401, (method, path, r.status_code)
        assert r.json()["error"]["code"] == 401


def test_csrf_checks():
    c, _ = signup()
    no_header = TestClient(app, cookies=c.cookies)
    assert no_header.post("/account/keys", json={"label": "x"}).status_code == 403
    assert c.post("/account/keys", json={"label": "x"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/account/keys", json={"label": "x"}, headers={"Referer": "https://evil.example/page"}).status_code == 403
    assert c.post("/account/keys", json={"label": "x"}, headers={"Origin": "null"}).status_code == 403
    assert c.post("/account/keys", json={"label": "x"}, headers={"Origin": "http://testserver"}).status_code == 200
    assert no_header.get("/account/keys").status_code == 200  # reads don't change state
    # Login and signup are protected too.
    assert TestClient(app).post("/auth/login", json={"email": "a@b.cc", "password": "12345678"}).status_code == 403


# ---------------- keys ----------------

def test_key_lifecycle():
    c, _ = signup()
    created = new_key(c, "Production")
    raw = created["api_key"]
    assert raw.startswith("ab_") and created["label"] == "Production" and created["active"]

    listed = c.get("/account/keys").json()["data"]
    assert [k["id"] for k in listed] == [created["id"]]
    assert "api_key" not in listed[0] and "key_hash" not in listed[0]
    assert listed[0]["last_used_at"] is None

    assert TestClient(app).post("/v1/chat/completions", headers=bearer(raw), json=CHAT).status_code == 200
    assert c.get("/account/keys").json()["data"][0]["last_used_at"]

    rotated = c.post(f"/account/keys/{created['id']}/rotate").json()
    new_raw = rotated["api_key"]
    assert new_raw != raw and rotated["label"] == "Production" and rotated["replaces"] == created["id"]
    assert TestClient(app).post("/v1/chat/completions", headers=bearer(raw), json=CHAT).status_code == 401
    assert TestClient(app).post("/v1/chat/completions", headers=bearer(new_raw), json=CHAT).status_code == 200
    assert c.post(f"/account/keys/{created['id']}/rotate").status_code == 409  # already revoked

    revoked = c.post(f"/account/keys/{rotated['id']}/revoke").json()
    assert revoked["active"] is False and revoked["revoked_at"]
    assert TestClient(app).post("/v1/chat/completions", headers=bearer(new_raw), json=CHAT).status_code == 401

    assert c.delete(f"/account/keys/{rotated['id']}").json() == {"id": rotated["id"], "deleted": True}
    assert [k["id"] for k in c.get("/account/keys").json()["data"]] == [created["id"]]
    # Usage from the deleted key is kept.
    assert c.get("/account/usage").json()["totals"]["requests"] == 2


def test_key_limit():
    c, _ = signup()
    keys = [new_key(c, f"k{i}") for i in range(5)]
    r = c.post("/account/keys", json={"label": "one too many"})
    assert r.status_code == 409 and "at most 5" in r.json()["error"]["message"]
    c.post(f"/account/keys/{keys[0]['id']}/revoke")
    assert c.post("/account/keys", json={"label": "after revoke"}).status_code == 200


def test_users_are_isolated():
    a, _ = signup()
    b, _ = signup()
    ka = new_key(a, "A's key")
    TestClient(app).post("/v1/chat/completions", headers=bearer(ka["api_key"]), json=CHAT)

    assert b.get("/account/keys").json()["data"] == []
    for method, path in [("post", f"/account/keys/{ka['id']}/rotate"), ("post", f"/account/keys/{ka['id']}/revoke"),
                         ("delete", f"/account/keys/{ka['id']}")]:
        assert getattr(b, method)(path).status_code == 404
    assert b.get("/account/usage").json()["totals"]["requests"] == 0
    # A's key is untouched.
    assert TestClient(app).get("/v1/models", headers=bearer(ka["api_key"])).status_code == 200
    assert a.get("/account/keys").json()["data"][0]["active"] is True


def test_usage_counts_only_own_keys():
    a, _ = signup()
    b, _ = signup()
    ka1, ka2, kb = new_key(a, "one")["api_key"], new_key(a, "two")["api_key"], new_key(b)["api_key"]
    anon = TestClient(app)
    anon.post("/v1/chat/completions", headers=bearer(ka1), json={"messages": [{"role": "user", "content": "Menene amfanin ruwa?"}]})
    anon.post("/v1/translate", headers=bearer(ka2), json={"text": "Good morning", "target": "yo", "source": "en"})
    anon.post("/v1/detect-language", headers=bearer(ka2), json={"text": "Kedu ka ị mere?"})
    anon.post("/v1/chat/completions", headers=bearer(kb), json=CHAT)

    u = a.get("/account/usage?days=30").json()
    assert u["totals"]["requests"] == 3 and u["totals"]["successful"] == 3 and u["totals"]["success_rate"] == 1.0
    assert u["totals"]["median_latency_ms"] is not None
    assert u["by_endpoint"] == {"chat": 1, "translate": 1, "detect": 1}
    assert u["by_language"]["ha"] == 1
    assert len(u["per_day"]) == 30 and u["per_day"][-1]["requests"] == 3
    assert sorted(k["requests"] for k in u["by_key"]) == [1, 2]
    assert b.get("/account/usage").json()["totals"]["requests"] == 1
    assert a.get("/account/usage?days=0").status_code == 422


# ---------------- beta keys ----------------

def test_beta_key_still_works_and_can_be_assigned():
    anon = TestClient(app)
    r = anon.post("/v1/signup", json={"name": "Old Tester", "email": "old@example.com", "code": "beta"})
    assert r.status_code == 200
    raw = r.json()["api_key"]
    assert anon.post("/v1/chat/completions", headers=bearer(raw), json=CHAT).status_code == 200
    kid = next(k["id"] for k in anon.get("/admin/keys", headers=ADMIN).json() if k["prefix"] == raw[:8])

    c, email = signup()
    assert c.get("/account/keys").json()["data"] == []  # never attached automatically
    assert anon.post(f"/admin/keys/{kid}/assign", json={"user_email": email}).status_code == 401
    assert anon.post(f"/admin/keys/{kid}/assign", headers=ADMIN, json={"user_email": "nobody@example.com"}).status_code == 404
    r = anon.post(f"/admin/keys/{kid}/assign", headers=ADMIN, json={"user_email": email.upper()})
    assert r.status_code == 200 and r.json()["label"] == "Beta key"

    keys = c.get("/account/keys").json()["data"]
    assert [k["id"] for k in keys] == [kid]
    assert anon.post("/v1/chat/completions", headers=bearer(raw), json=CHAT).status_code == 200
    assert c.get("/account/usage").json()["totals"]["requests"] == 2  # history from before the assignment counts


# ---------------- migration ----------------

def test_migration_adds_account_columns(tmp_path):
    """A v2.1.1 database (api_keys without the new columns) is upgraded in place, keeping its data."""
    import sqlite3
    db = tmp_path / "v211.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE api_keys (id INTEGER PRIMARY KEY, name VARCHAR(120), email VARCHAR(200), "
                "organisation VARCHAR(200), prefix VARCHAR(16), key_hash VARCHAR(64) UNIQUE, active BOOLEAN, created_at DATETIME)")
    con.execute("INSERT INTO api_keys VALUES (1, 'Beta', 'b@x.com', '', 'ab_test1', ?, 1, '2026-10-01 10:00:00')",
                (security.hash_key("ab_test1-raw"),))
    con.execute("CREATE TABLE usage_logs (id INTEGER PRIMARY KEY, key_id INTEGER, endpoint VARCHAR(60), backend VARCHAR(20))")
    con.execute("INSERT INTO usage_logs VALUES (1, 1, 'chat', 'gpu')")
    con.commit(); con.close()
    code = ("from app.db import init_db, engine; from sqlalchemy import inspect, text; init_db(); init_db();"
            "i = inspect(engine); print(sorted(c['name'] for c in i.get_columns('api_keys')));"
            "print(sorted(i.get_table_names()));"
            "print(engine.connect().execute(text('SELECT name, active, user_id, label FROM api_keys')).all());"
            "print(engine.connect().execute(text('SELECT count(*) FROM usage_logs')).scalar())")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.dirname(__file__)), env={**os.environ, "DATABASE_URL": f"sqlite:///{db}"})
    assert out.returncode == 0, out.stderr
    cols, tables, rows, logs = out.stdout.strip().splitlines()
    for col in ("user_id", "label", "last_used_at", "revoked_at", "deleted_at"):
        assert f"'{col}'" in cols
    assert "'users'" in tables and "'user_sessions'" in tables
    assert rows == "[('Beta', 1, None, '')]" and logs == "1"


def test_migration_sql_for_postgres():
    """The statements run on Render's Postgres: add-only, all nullable or defaulted."""
    from app import db

    sql = db.migration_sql({"id", "name", "email", "organisation", "prefix", "key_hash", "active", "created_at"},
                           "postgresql")
    assert sql == [
        "ALTER TABLE api_keys ADD COLUMN user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE api_keys ADD COLUMN label VARCHAR(60) DEFAULT ''",
        "ALTER TABLE api_keys ADD COLUMN last_used_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE api_keys ADD COLUMN revoked_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE api_keys ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE",
        "CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys (user_id)",
    ]
    assert db.migration_sql({"user_id", "label", "last_used_at", "revoked_at", "deleted_at"}) == []
