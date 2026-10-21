"""Check the v2.1.1 -> v2.2.0 database upgrade against a real database (meant for Postgres).

  cd gateway
  DATABASE_URL=postgresql://user:pass@localhost/atlasbridge_upgrade_test python scripts/check_upgrade.py

Use an empty, throwaway database: the script refuses to run if AtlasBridge tables already exist.
It (a) creates the schema exactly as v2.1.1's create_all did (only api_keys and usage_logs) with
sample rows, (b) runs the new init_db() twice, and (c) checks that the old rows are unchanged, that
old keys still authenticate (and a revoked one still doesn't), and that the new tables and columns
exist. Pass --drop to remove the tables it created afterwards. Exits 1 if any check fails.
"""

import os
import sys
from pathlib import Path

if not os.environ.get("DATABASE_URL"):
    sys.exit("Set DATABASE_URL to an empty, throwaway database first.")
# Settings are read on import: no model server, a known admin token, and no previews in the log.
os.environ.update(MOCK_UPSTREAM="1", ADMIN_TOKEN="upgrade-check", SIGNUP_CODE="upgrade-check", LOG_CONTENT="0",
                  SESSION_SECRET="upgrade-check")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.security import hash_key  # noqa: E402

# DDL that v2.1.1 (commit 5ed516e) created on Postgres, compiled from its db.py models.
V211_SCHEMA = """
CREATE TABLE api_keys (
    id SERIAL NOT NULL,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(200) NOT NULL,
    organisation VARCHAR(200) NOT NULL,
    prefix VARCHAR(16) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    active BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_api_keys_key_hash ON api_keys (key_hash);
CREATE INDEX ix_api_keys_prefix ON api_keys (prefix);
CREATE TABLE usage_logs (
    id SERIAL NOT NULL,
    key_id INTEGER,
    endpoint VARCHAR(60) NOT NULL,
    language VARCHAR(16) NOT NULL,
    status_code INTEGER NOT NULL,
    latency_ms FLOAT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    streamed BOOLEAN NOT NULL,
    client VARCHAR(120) NOT NULL,
    prompt_preview TEXT NOT NULL,
    reply_preview TEXT NOT NULL,
    error TEXT NOT NULL,
    backend VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(key_id) REFERENCES api_keys (id)
);
CREATE INDEX ix_usage_logs_created_at ON usage_logs (created_at);
CREATE INDEX ix_usage_logs_key_id ON usage_logs (key_id);
"""

ACTIVE_RAW, REVOKED_RAW = "ab_upgradeCheckActiveKey0000000000", "ab_upgradeCheckRevokedKey000000000"
KEYS = [  # id, name, email, organisation, raw key, active
    (1, "Ada Tester", "ada@example.com", "NAIC", ACTIVE_RAW, True),
    (2, "Old Revoked", "old@example.com", "", REVOKED_RAW, False),
]
LOGS = [  # id, key_id, endpoint, language, status, latency, backend
    (1, 1, "chat", "ha", 200, 812.5, "gpu"),
    (2, 1, "translate", "yo", 200, 640.0, "cpu-backup"),
    (3, 2, "chat", "ig", 502, 30.1, ""),
]
NEW_TABLES = {"users", "user_sessions"}
NEW_KEY_COLUMNS = {"user_id", "label", "last_used_at", "revoked_at", "deleted_at"}

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        failures.append(what)


def snapshot(conn) -> tuple[list, list]:
    keys = conn.execute(text("SELECT id, name, email, organisation, prefix, key_hash, active, created_at "
                             "FROM api_keys ORDER BY id")).all()
    logs = conn.execute(text("SELECT id, key_id, endpoint, language, status_code, latency_ms, backend, created_at "
                             "FROM usage_logs ORDER BY id")).all()
    return [tuple(r) for r in keys], [tuple(r) for r in logs]


def main() -> None:
    print(f"Database: {engine.url.render_as_string(hide_password=True)} ({engine.dialect.name})")
    existing = set(inspect(engine).get_table_names()) & ({"api_keys", "usage_logs"} | NEW_TABLES)
    if existing:
        sys.exit(f"Refusing to run: {sorted(existing)} already exist. Use an empty, throwaway database.")

    # (a) the v2.1.1 schema and some data
    ddl = V211_SCHEMA if engine.dialect.name == "postgresql" else V211_SCHEMA.replace("SERIAL", "INTEGER")
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in ddl.split(";"))):
            conn.execute(text(stmt))
        for kid, name, email, org, raw, active in KEYS:
            conn.execute(text("INSERT INTO api_keys (id, name, email, organisation, prefix, key_hash, active, created_at) "
                              "VALUES (:i, :n, :e, :o, :p, :h, :a, '2026-10-05 09:00:00+00')"),
                         dict(i=kid, n=name, e=email, o=org, p=raw[:8], h=hash_key(raw), a=active))
        for lid, kid, ep, lang, status, lat, backend in LOGS:
            conn.execute(text("INSERT INTO usage_logs (id, key_id, endpoint, language, status_code, latency_ms, "
                              "prompt_tokens, completion_tokens, streamed, client, prompt_preview, reply_preview, error, "
                              "backend, created_at) VALUES (:i, :k, :ep, :l, :s, :lat, 10, 20, false, 'curl/8', '', '', '', "
                              ":b, '2026-10-06 12:00:00+00')"),
                         dict(i=lid, k=kid, ep=ep, l=lang, s=status, lat=lat, b=backend))
        if engine.dialect.name == "postgresql":  # the rows above set ids by hand; move the sequences past them
            conn.execute(text("SELECT setval('api_keys_id_seq', (SELECT max(id) FROM api_keys))"))
            conn.execute(text("SELECT setval('usage_logs_id_seq', (SELECT max(id) FROM usage_logs))"))
        before = snapshot(conn)
    print(f"Created the v2.1.1 schema with {len(KEYS)} keys and {len(LOGS)} usage rows.")

    # (b) upgrade, twice: the second run must be a no-op
    init_db()
    init_db()
    print("Ran init_db() twice.")

    # (c) checks
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    check(NEW_TABLES <= tables, f"new tables exist: {sorted(NEW_TABLES)}")
    key_cols = {c["name"]: c for c in insp.get_columns("api_keys")}
    check(NEW_KEY_COLUMNS <= set(key_cols), f"new api_keys columns exist: {sorted(NEW_KEY_COLUMNS)}")
    check(all(key_cols[c]["nullable"] for c in NEW_KEY_COLUMNS & set(key_cols)), "new api_keys columns are nullable")
    check("ix_api_keys_user_id" in {i["name"] for i in insp.get_indexes("api_keys")}, "index ix_api_keys_user_id exists")
    check(any(fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"]
              for fk in insp.get_foreign_keys("api_keys")), "api_keys.user_id references users(id)")

    with engine.connect() as conn:
        check(snapshot(conn) == before, "existing api_keys and usage_logs rows are unchanged")
        new_vals = conn.execute(text("SELECT user_id, label, last_used_at, revoked_at, deleted_at FROM api_keys")).all()
    check(all(tuple(r) == (None, "", None, None, None) for r in new_vals),
          "old keys have no user, an empty label and no new timestamps")

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        ok = {"Authorization": f"Bearer {ACTIVE_RAW}"}
        check(c.get("/v1/models", headers=ok).status_code == 200, "old active key authenticates (/v1/models)")
        r = c.post("/v1/chat/completions", headers=ok, json={"messages": [{"role": "user", "content": "Sannu"}]})
        check(r.status_code == 200, "old active key can chat (/v1/chat/completions, mock model)")
        check(c.get("/v1/models", headers={"Authorization": f"Bearer {REVOKED_RAW}"}).status_code == 401,
              "old revoked key is still rejected")
        usage = c.get("/v1/usage", headers=ok).json()
        check(sum(e["requests"] for e in usage.get("endpoints", [])) == 3, "old key's /v1/usage includes its old rows")

        # The new account features work on the upgraded database too.
        web = {"X-AtlasBridge-Client": "web"}
        r = c.post("/auth/signup", headers=web, json={"email": "ada@example.com", "password": "upgrade-check-pw",
                                                      "name": "Ada Tester", "code": "upgrade-check"})
        check(r.status_code == 200, "account signup works")
        check(c.get("/account/keys").json().get("data") == [], "old key isn't attached to the account automatically")
        r = c.post("/admin/keys/1/assign", headers={"Authorization": "Bearer upgrade-check"},
                   json={"user_email": "ada@example.com"})
        check(r.status_code == 200, "admin can assign the old key to the account")
        usage = c.get("/account/usage?days=365").json()
        check(usage.get("totals", {}).get("requests", 0) >= 1, "account usage reads the old key's logs")
        check(c.get("/v1/models", headers=ok).status_code == 200, "old key still works after assignment")
        r = c.post("/account/keys", headers=web, json={"label": "New"})
        check(r.status_code == 200 and c.get("/v1/models", headers={"Authorization": f"Bearer {r.json().get('api_key')}"}).status_code == 200,
              "a new key can be created and used (id sequence not clashing with old rows)")

    if "--drop" in sys.argv:
        with engine.begin() as conn:
            for t in ("usage_logs", "user_sessions", "api_keys", "users"):
                conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        print("Dropped the test tables (--drop).")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
