# AtlasBridge

**An OpenAI-compatible developer gateway and Python SDK for N-ATLaS, Nigeria's multilingual LLM (English, Hausa, Igbo, Yoruba).**

N-ATLaS is open, but using it today means downloading an 8B-parameter model, finding a GPU, and wiring up its chat template yourself. Most Nigerian developers can't do that. AtlasBridge hosts N-ATLaS behind the API shape the whole ecosystem already speaks. Any app that uses the OpenAI SDK, LangChain or plain `fetch` can switch to N-ATLaS by changing its `base_url`.

> N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies.

Built for the National AI Innovation Challenge 2026, Problem Statement 1 (Developer Infrastructure).

**Current version: v2.1.0.**

**Live:** https://atlasbridge.onrender.com · **Repo:** https://github.com/Kingsmichaei/atlasbridge See [CHANGELOG.md](CHANGELOG.md).

## What's included

| Part | Path | What it does |
|---|---|---|
| Serving notebook | `serving/atlasbridge_serve_kaggle.ipynb` | Runs `NCAIR1/N-ATLaS` on a GPU (Kaggle 2×T4) as an OpenAI-compatible server and exposes it through a secure tunnel |
| CPU backup | `serving/cpu-backup/` | Always-on Hugging Face Space: N-ATLaS Q4_K_M GGUF on llama.cpp. The gateway fails over to it automatically when the GPU is off |
| Gateway | `gateway/` | FastAPI service: API keys, rate limits, streaming chat, translation, language detection, usage logging and a validation report |
| Python SDK + CLI | `sdk/` | `pip install` client: `chat`, `stream`, `translate`, `detect_language`, multi-turn `Conversation`, `atlasbridge` CLI |
| Playground | `gateway/app/static/index.html` | Web page served at `/`: beta signup, chat in all four languages, translate, detect, and copy-paste code for each language |

## Architecture

```
Your app ──(OpenAI SDK / AtlasBridge SDK / HTTP)──▶ AtlasBridge gateway (FastAPI, Render)
                                                     │  API keys · rate limits · usage logs (Postgres)
                                                     │  N-ATLaS prompt defaults · translate/detect tasks
                                                     ▼
              ┌──────────────────────────────────────┴──────────────────────────────┐
              ▼ primary (when healthy)                               ▼ automatic fallback
  N-ATLaS GPU server (Kaggle 2×T4)                      N-ATLaS CPU backup (HF Space, always on)
  NCAIR1/N-ATLaS, fp16, transformers                    N-ATLaS Q4_K_M GGUF, llama.cpp, 2 vCPU
```

**Language handling.** N-ATLaS is an 8B model, and left to itself it sometimes answers in the wrong Nigerian language, especially in conversations that switch languages. The gateway detects the language of each message offline (97% on a held-out set of everyday phrases typed with or without diacritics) and names the reply language in the system prompt. Developers can override it with `language`.

**How the integration works.** Every model call goes to `NCAIR1/N-ATLaS`, and no other model is used. The serving layer loads the official weights and applies N-ATLaS's own chat template (including its `date_string` system header). It uses the generation settings recommended on the model card: temperature 0.1 and repetition penalty 1.12. The gateway adds a default multilingual system prompt and builds translation and language-ID tasks as N-ATLaS prompts.

## Quick start (using a deployed gateway)

```python
from openai import OpenAI

client = OpenAI(api_key="ab_...", base_url="https://<gateway>/v1")
r = client.chat.completions.create(model="n-atlas",
        messages=[{"role": "user", "content": "Menene amfanin ruwa ga jikin dan Adam?"}])
print(r.choices[0].message.content)
```

```python
# pip install "git+https://github.com/Kingsmichaei/atlasbridge#subdirectory=sdk"
from atlasbridge import AtlasBridge

ab = AtlasBridge(api_key="ab_...", base_url="https://<gateway>")
ab.chat("Kedu ka ị mere?")                     # replies in Igbo
ab.chat("Tell me about Kano", language="hausa")    # force the reply language
ab.translate("Wash your hands before eating.", to="hausa")
ab.detect_language("Kini anfaani omi fun ara eniyan?")   # {'language': 'yo', ...}
for piece in ab.stream("Tell me about Kano"): print(piece, end="")
```

CLI: `export ATLASBRIDGE_API_KEY=... ATLASBRIDGE_BASE_URL=...`, then `atlasbridge chat "Sannu"` or `atlasbridge translate --to ig "Good morning"`.

## API reference

All endpoints take `Authorization: Bearer <key>`. Errors use the OpenAI error shape. Interactive docs are at `/docs`.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/v1/models` | | Lists `n-atlas` |
| POST | `/v1/chat/completions` | OpenAI chat format; `stream`, `temperature`, `top_p`, `max_tokens`, `repetition_penalty`, plus `language` (`auto`/`en`/`ha`/`ig`/`yo`) | In `auto`, the gateway detects the user's language and tells N-ATLaS to reply in it. Adds `x_atlasbridge.detected_language` and `reply_language` to the response |
| POST | `/v1/translate` | `{text, target, source="auto"}` | `en`, `ha`, `ig`, `yo` |
| POST | `/v1/detect-language` | `{text, method="heuristic" or "model"}` | Fast offline rules, or ask N-ATLaS |
| GET | `/v1/usage` | | Your own usage |
| POST | `/v1/signup` | `{name, email, organisation, code}` | Beta key with invite code |
| GET | `/health` | | Gateway and model status |

Admin (`Bearer ADMIN_TOKEN`): `POST /admin/keys`, `GET /admin/keys`, `POST /admin/keys/{id}/revoke`, `GET /admin/report[?format=csv]`.

## Running it yourself

**1. Model server (GPU).** Import `serving/atlasbridge_serve_kaggle.ipynb` into Kaggle and set Accelerator to GPU T4 x2 with Internet on. Add the secrets `HF_TOKEN` (with access granted to `NCAIR1/N-ATLaS`) and `UPSTREAM_KEY`, then Run All. Copy the printed `UPSTREAM_URL`. The notebook works on any CUDA machine. `serving/fallback_server.py` is the same server as a standalone script.

**2. Gateway.**
```bash
cd gateway
pip install -r requirements.txt
cp .env.example .env    # set UPSTREAM_URL, UPSTREAM_KEY, ADMIN_TOKEN (or MOCK_UPSTREAM=1 to develop with no GPU)
uvicorn app.main:app --reload
pytest -q               # 23 tests: auth, streaming, OpenAI-SDK compatibility, proxy path, GPU→CPU failover, rate limits, report, language ID
```

**3. CPU backup (optional, recommended).** Create a Hugging Face Space (SDK: **Docker**, hardware: free **CPU basic**) and upload `serving/cpu-backup/Dockerfile` and `README.md`. Add the Space secret `LLAMA_API_KEY`. The first start downloads about 4.9 GB and takes a few minutes. Then set `UPSTREAM_FALLBACK_URL=https://<user>-<space>.hf.space` and `UPSTREAM_FALLBACK_KEY` on the gateway. The `keep-awake` GitHub Action pings the gateway and the Space every 10 minutes: set the repository variables `GATEWAY_URL` and `BACKUP_URL`.

**Deploy:** in Render, choose New → Blueprint and point it at this repo. `render.yaml` creates the web service and a Postgres database. Set `UPSTREAM_URL` and `UPSTREAM_KEY` in the dashboard.

## Validation

Every request is logged with the tester, endpoint, detected language, latency, token counts, status and client (SDK, OpenAI SDK or browser). With `LOG_CONTENT=1`, a 300-character preview of the prompt and reply is also kept. `GET /admin/report` summarises usage per tester and per language, and `?format=csv` exports the raw log for the validation evidence.

## Limitations

- Model quality comes from N-ATLaS v1. Its own human evaluation scores Yoruba lowest (2.69/5), against Hausa 3.98, Igbo 3.87 and English 4.21. Translation and language ID inherit this.
- Nigerian Pidgin isn't an officially supported N-ATLaS language.
- The GPU server runs on free Kaggle sessions, so it isn't always on. When it's off, the gateway falls back to the CPU backup, which is always on but slower (2–5 tokens/s, replies capped at 256 tokens). It uses a community 4-bit quantisation of N-ATLaS, so its answers can differ slightly from the fp16 model. Every response reports which `backend` served it.
- The N-ATLaS licence limits deployments to 1,000 monthly active end users without a commercial licence from Awarri. AtlasBridge is a beta under that cap.

## Licence and attribution

AtlasBridge code: MIT. N-ATLaS model: Awarri Technologies / FMCIDE Open-Source Research and Innovation License. *N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies.*
