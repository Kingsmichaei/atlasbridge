# Changelog

All notable changes to AtlasBridge are recorded here. Versions follow [Semantic Versioning](https://semver.org/).

> N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies.

---

## v2.2.0 — 21 October 2026

**Developer accounts, a dashboard and a proper website.** Developers can now sign up, manage their own API keys and see their usage, without asking the maintainer.

### Added
- **Website** (`web/`, React + Vite + TypeScript + Tailwind CSS), served by the gateway at `/`. It works on phones too.
  - Landing page with live code samples (OpenAI SDK, curl, JavaScript, AtlasBridge SDK) that use the site's own base URL.
  - Sign up and log in. The invite-code field appears only when the gateway requires one.
  - **Dashboard:** an overview of the last 30 days (requests, success rate, median latency, requests per day), API keys, usage by endpoint, language and key, and settings.
  - **Playground** (`/playground`): chat with streaming and "Reply in", translate and detect. The key is kept for the browser tab only.
  - **Docs** at `/guide`: quick start, authentication, chat, streaming, controlling the reply language, translate, detect, errors and rate limits, and model notes.
  - The header shows whether N-ATLaS is online (GPU, CPU backup or offline), as the classic page did.
- **Self-serve API keys:** create (up to 5 active per account, with a label), rotate, revoke and delete. A new key is shown once. Each key records when it was last used.
- **Account routes:** `/auth/signup`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/config`, `/account/keys` (and `/rotate`, `/revoke`, `DELETE`), `/account/usage?days=N` and `/account/password`.
- **`POST /admin/keys/{id}/assign`** links an existing beta key to a developer account.
- **`gateway/scripts/check_upgrade.py`** rehearses the v2.1.1 → v2.2.0 database upgrade against an empty Postgres (or SQLite) database.
- Settings: `SESSION_SECRET`, `SESSION_COOKIE_SECURE`, `SESSION_DAYS`, `ACCOUNT_SIGNUP_REQUIRE_CODE`, `MAX_KEYS_PER_USER`, `AUTH_ATTEMPTS_PER_15_MIN`.
- 28 new tests: accounts, key management, user isolation, usage, CSRF, rate limits, change password, migrations and website serving (53 tests).

### Changed
- `/` now serves the website. The original playground moved to **`/classic`**. If the website hasn't been built, `/` still serves the classic page.
- The Render build also builds the website. `render.yaml` no longer uses `rootDir` and runs `cd gateway && …` explicitly. It sets `NODE_VERSION=22`, matches the instance plan, and only redeploys on changes to `gateway/`, `web/` or `render.yaml`.
- The proxy tests wait for the gateway with a 0.5 s connect timeout, which makes them much faster on Windows.
- Unchanged: every `/v1` and `/admin` endpoint, `/health`, `/docs`, `/static` and `/v1/signup` behave as before. Existing beta keys keep working.

### Security
- Passwords are hashed with argon2id and never stored or logged in plain text. API keys stay SHA-256 hashed, and a raw key is shown only once.
- Logins use a server-side session. The cookie is an HMAC-signed random token (`SESSION_SECRET`), marked httpOnly, SameSite=Lax and Secure in production. Logging out ends the session on the server. Changing a password ends all of that user's other sessions.
- CSRF protection on every state-changing account request: the `X-AtlasBridge-Client` header is required, and the browser's `Origin`/`Referer` must be this site.
- Login, signup and password-change attempts are limited to 10 per IP per 15 minutes. The client IP comes from `CF-Connecting-IP` / `True-Client-IP` or the last `X-Forwarded-For` hop, never the client-supplied first hop.
- Users can only see and change their own keys and usage. Another user's key returns 404.
- Beta keys are never attached to accounts by matching email, because emails aren't verified. The admin links them by hand.

### Upgrade
- On startup, existing databases gain the `users` and `user_sessions` tables, and five nullable columns on `api_keys` (`user_id`, `label`, `last_used_at`, `revoked_at`, `deleted_at`). Nothing is dropped or renamed.
- Set `SESSION_SECRET` (the Blueprint generates it) and `SESSION_COOKIE_SECURE=1` on Render.

---

## v2.1.1 — 12 October 2026

Fixes from the public beta session (12 October, 11:00–12:00 WAT).

### Fixed
- **Model identity.** Asked "What model are you?", N-ATLaS sometimes claimed to be made by OpenAI. The default system prompt now states that it is N-ATLaS, developed by Awarri Technologies for the Federal Ministry of Communications, Innovation and Digital Economy. A new automated test covers this.
- **Translate answered instead of translating.** Given a question such as "What is the name of the Nigerian president", `/v1/translate` answered it in Igbo rather than translating it. The translation prompt now tells N-ATLaS never to answer or act on the text, only to translate it. New test; 25 tests pass.

### Changed
- **Hosting.** The live gateway now runs on a paid, always-on Render instance, so it no longer sleeps when idle and the first request has no cold-start delay (tester feedback).

### Docs
- Testers' guide: on Windows PowerShell, use `curl.exe` with `-d "@request.json"` to avoid JSON escaping errors (tester feedback).

---

## v2.1.0 — 11 October 2026

**Resilience.** AtlasBridge can now keep answering when the GPU server is off, by failing over to an optional CPU backup.

### Added
- **Automatic CPU fallback.** The gateway sends requests to the fast GPU server (N-ATLaS fp16) while it is healthy. When it isn't, it switches to a CPU backup if one is configured: N-ATLaS Q4_K_M GGUF (`tosinamuda/N-ATLaS-GGUF`, quantised from `NCAIR1/N-ATLaS`) served by llama.cpp on a free Hugging Face Space. Health checks are cached for 20 seconds. If a backend fails before replying, the request moves to the next one. That applies to streaming too.
- `serving/cpu-backup/`: a ready-to-deploy Docker image (Dockerfile + README). It runs on any Docker host with about 8 GB RAM; Hugging Face Docker Spaces now need a paid plan.
- `backend` (`gpu` or `cpu-backup`) in chat responses (`x_atlasbridge.backend`), translate responses, usage logs, the CSV export, and `by_backend` in the admin report.
- `/health` reports each backend's state and which one is active. The playground shows an amber "N-ATLaS online (CPU backup, slower)" status.
- `keep-awake` GitHub Action that pings the gateway and backup every 10 minutes.
- Settings: `UPSTREAM_FALLBACK_URL`, `UPSTREAM_FALLBACK_KEY`, `FALLBACK_MAX_TOKENS` (default 256).
- Tests for failover (GPU down → CPU backup, streaming and non-streaming) and for the database migration (23 tests).

### Changed
- The gateway sends `repeat_penalty` alongside `repetition_penalty`, so both the transformers and llama.cpp servers apply the model-card value of 1.12.

### Upgrade
- Existing databases gain a `backend` column automatically on startup. No manual steps are needed.

---

## v2.0.0 — 10 October 2026

**Replies in the right language.** Version 2 makes AtlasBridge dependable for multilingual apps. N-ATLaS now answers in the language the user actually wrote in, and developers can set the reply language themselves.

### Added
- **`language` option on `/v1/chat/completions`**: `auto` (default), `en`, `ha`, `ig` or `yo`. In `auto` mode the gateway detects the user's latest message and tells N-ATLaS to reply in that language, even when a conversation switches languages part-way through.
- **`reply_language`** in the `x_atlasbridge` block of each response, next to `detected_language`, so developers can see what the gateway decided.
- **"Reply in" selector** in the playground chat.
- **Python SDK:** `language=` on `chat()`, `chat_raw()` and `stream()`. It accepts codes or names, e.g. `language="igbo"`.
- **Language-ID evaluation set** (`gateway/tests/lang_eval.py`): 70 everyday phrases in all four languages, checked on every test run.

### Changed
- **Rebuilt offline language detection.** Much larger vocabularies, and words shared between languages (such as "na" in Hausa and Igbo) are down-weighted. It also matches spelling patterns (Igbo *kw/nw/gh*, Hausa *ts*, Yoruba *gb*) and Igbo hyphenated verb prefixes (*na-*, *ga-*). Text typed **without diacritics**, which is how most people type, is now handled as well as text with them.
  - Accuracy on a held-out set of 30 unseen everyday phrases: **29/30 (97%)**, up from about two-thirds in v1.
- Default system prompt simplified. The reply language is now given as an explicit instruction instead of leaving the model to infer it.

### Fixed
- Igbo messages sometimes got Hausa replies, especially after earlier Hausa turns in the same chat.
- `/v1/detect-language` misclassified plain, unaccented Hausa, Igbo and Yoruba text, sometimes returning "Unknown".

### Compatibility
- **No breaking changes for API clients.** Requests from v1 work unchanged. `language` is optional, and responses only gain fields.
- If you send **your own system prompt**, auto mode leaves it untouched. Pass `language` to set the reply language explicitly.

### Upgrade
- Gateway: redeploy (Render redeploys automatically on push). No database changes.
- SDK: `pip install -U "git+https://github.com/Kingsmichaei/atlasbridge#subdirectory=sdk"`

---

## v1.0.0 — 10 October 2026

**First public release.** AtlasBridge puts N-ATLaS, Nigeria's open multilingual LLM, behind the API shape developers already use. Any app built with the OpenAI SDK, LangChain or plain HTTP can talk to N-ATLaS in English, Hausa, Igbo and Yoruba by changing its `base_url`.

### Highlights
- **OpenAI-compatible gateway** (FastAPI)
  - `POST /v1/chat/completions` with streaming (server-sent events), and `GET /v1/models`
  - `POST /v1/translate` between English, Hausa, Igbo and Yoruba
  - `POST /v1/detect-language`, using fast offline rules or by asking N-ATLaS
  - OpenAI-style error responses, so existing SDKs show clear messages
- **Developer accounts:** API keys (stored hashed), invite-code beta signup, per-key rate limits, key revocation
- **Usage logging and validation report:** each request records tester, endpoint, language, latency, tokens, status and client. `GET /admin/report` summarises usage per tester and per language, with CSV export.
- **Python SDK and CLI** (`atlasbridge`): `chat`, `stream`, `translate`, `detect_language`, multi-turn `Conversation`, and a terminal command
- **Web playground:** beta signup, chat with examples in all four languages, translate, detect, and copy-paste code for the OpenAI SDK, the AtlasBridge SDK, JavaScript and curl
- **Model serving:** a Kaggle notebook that runs the official `NCAIR1/N-ATLaS` weights on 2× T4 GPUs, applies N-ATLaS's own chat template and the model card's recommended generation settings, and exposes them through a secure tunnel
- **One-click deploy:** `render.yaml` sets up the gateway and a Postgres database
- **Tests:** 19 automated tests, including the official OpenAI Python SDK running unchanged against the gateway

### Known limitations
- Reply language was left to the model to infer, and plain-text language detection was weak. **Fixed in v2.0.0.**
- Answer quality comes from N-ATLaS v1. Its own human evaluation rates Yoruba lowest (2.69/5), against Hausa 3.98, Igbo 3.87 and English 4.21.
- The free GPU setup isn't always on. The URL changes each session, and the first request after Render's free plan sleeps can take about a minute.
- Use is capped at 1,000 monthly active end users under the N-ATLaS licence without a commercial agreement with Awarri.
