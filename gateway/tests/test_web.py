"""Serving the website (web/dist) next to the API, with and without a build."""
import pytest
from fastapi.testclient import TestClient

from app import web
from app.main import app

INDEX = "<!doctype html><title>AtlasBridge SPA</title><div id=root></div>"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "brand").mkdir()
    (tmp_path / "index.html").write_text(INDEX)
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log('app')")
    (tmp_path / "brand" / "logo.png").write_bytes(b"\x89PNG fake")
    (tmp_path.parent / "secret.txt").write_text("outside dist")
    monkeypatch.setattr(web, "DIST", tmp_path)
    return tmp_path


@pytest.fixture
def no_dist(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "DIST", tmp_path / "missing")


def test_spa_served_at_root_and_client_routes(client, dist):
    for path in ["/", "/dashboard", "/dashboard/keys", "/guide", "/login?next=x"]:
        r = client.get(path)
        assert r.status_code == 200 and r.text == INDEX, path
        assert r.headers["cache-control"] == "no-cache"
    assert client.head("/dashboard").status_code == 200


def test_static_build_files(client, dist):
    r = client.get("/assets/index-abc123.js")
    assert r.status_code == 200 and "console.log" in r.text
    assert "immutable" in r.headers["cache-control"]
    assert client.get("/brand/logo.png").content == b"\x89PNG fake"
    # Missing files are real 404s, not the app shell.
    assert client.get("/assets/old-999.js").status_code == 404
    # No escaping the dist folder.
    for p in ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt"]:
        r = client.get(p)
        assert "outside dist" not in r.text, p


def test_backend_routes_win(client, dist):
    assert client.get("/health").json()["gateway"] == "ok"
    assert client.get("/api").json()["name"] == "AtlasBridge"
    assert "swagger" in client.get("/docs").text.lower()
    assert client.get("/openapi.json").json()["info"]["title"] == "AtlasBridge"
    assert client.get("/favicon.ico").status_code in (200, 204)
    assert client.get("/static/brand/favicon.svg").status_code == 200
    assert client.get("/auth/config").json() == {"signup_code_required": True}
    assert client.get("/v1/models").status_code == 401
    r = client.get("/classic")
    assert r.status_code == 200 and "AtlasBridge" in r.text and "SPA" not in r.text


def test_unmatched_backend_paths_keep_default_404(client, dist):
    for path in ["/v1/nope", "/admin/nope", "/account/nope", "/static/nope.png", "/docs/nope"]:
        r = client.get(path)
        assert r.status_code == 404 and r.json() == {"detail": "Not Found"}, path
    # Non-GET requests are never the website, and still 404 rather than 405.
    r = client.post("/dashboard")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}
    assert client.post("/v1/models").status_code == 405


def test_route_404s_keep_openai_shape(client, dist):
    c = TestClient(app, headers={"X-AtlasBridge-Client": "web"})
    c.post("/auth/signup", json={"email": "web-404@example.com", "password": "12345678", "name": "Web Test", "code": "beta"})
    r = c.post("/account/keys/999999/revoke")
    assert r.status_code == 404 and r.json()["error"]["message"] == "Key not found."


def test_without_build_root_is_classic_page_and_api_works(client, no_dist):
    r = client.get("/")
    assert r.status_code == 200 and "AtlasBridge" in r.text and "SPA" not in r.text
    assert client.get("/dashboard").status_code == 404
    assert client.get("/health").status_code == 200
    assert client.get("/classic").status_code == 200
