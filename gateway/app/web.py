"""Serve the website (web/dist, built by Vite) alongside the API.

Rather than a catch-all route, which would turn unknown POSTs into 405s, the site is served
from the 404 handler: when no backend route matched a GET/HEAD outside the backend prefixes,
serve the file from web/dist if there is one, otherwise index.html so the React router can
handle the path. Backend routes always win, and unmatched backend paths keep FastAPI's
default 404 body.

If web/dist hasn't been built, "/" serves the classic single-page playground and the API
works as before.
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

STATIC = Path(__file__).parent / "static"
DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

# First path segments that belong to the gateway, never to the website.
BACKEND = {"v1", "auth", "account", "admin", "static", "docs", "redoc", "openapi.json", "health", "api",
           "favicon.ico", "classic"}


def _dist_file(path: str) -> Path | None:
    """The file under DIST for this URL path, or None (also for anything escaping DIST)."""
    root = DIST.resolve()
    target = (root / path.lstrip("/")).resolve()
    if target != root and root in target.parents and target.is_file():
        return target
    return None


def site_response(request: Request) -> Response | None:
    """What the website serves for this request, or None to fall back to the normal 404."""
    if request.method not in ("GET", "HEAD"):
        return None
    path = request.url.path
    if path.strip("/").split("/", 1)[0] in BACKEND:
        return None
    index = DIST / "index.html"
    if not index.is_file():
        # No build: keep the gateway usable, with the classic page at "/".
        return FileResponse(STATIC / "index.html") if path == "/" else None
    if (f := _dist_file(path)) is not None:
        # Vite fingerprints everything under /assets/, so those can be cached forever.
        cache = "public, max-age=31536000, immutable" if path.startswith("/assets/") else "public, max-age=3600"
        return FileResponse(f, headers={"Cache-Control": cache})
    if "." in path.rsplit("/", 1)[-1]:
        return None  # a missing file (e.g. an old /assets/x.js) is a real 404, not the app shell
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


def install(app: FastAPI, error: Callable[[int, str], Response]) -> None:
    @app.get("/classic", include_in_schema=False)
    async def classic():
        return FileResponse(STATIC / "index.html")

    @app.exception_handler(404)
    async def _not_found(request: Request, exc: Exception):
        # Our own HTTPException(404, ...) from routes (e.g. "Key not found.") keeps the OpenAI error shape.
        if not (type(exc) is StarletteHTTPException and exc.detail == "Not Found"):
            return error(404, str(getattr(exc, "detail", "Not Found")))
        return site_response(request) or JSONResponse(status_code=404, content={"detail": "Not Found"})
