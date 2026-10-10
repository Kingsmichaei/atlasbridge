# Changelog

All notable changes to AtlasBridge are recorded here. Versions follow [Semantic Versioning](https://semver.org/).

> N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies.

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
- SDK: `pip install -U "git+https://github.com/<you>/atlasbridge#subdirectory=sdk"`

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
