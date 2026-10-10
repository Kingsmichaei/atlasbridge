import json, sys
fallback = open(sys.argv[1]).read()
out = sys.argv[2]

def md(s): return {"cell_type":"markdown","metadata":{},"source":s.strip("\n")}
def code(s): return {"cell_type":"code","metadata":{},"execution_count":None,"outputs":[],"source":s.strip("\n")}

cells = [
md("""
# AtlasBridge — serve N-ATLaS on Kaggle

Serves **NCAIR1/N-ATLaS** as an OpenAI-compatible API on a free Kaggle GPU and gives it a public URL for the AtlasBridge gateway.

**Before you run (one-time):**
1. On Hugging Face, open https://huggingface.co/NCAIR1/N-ATLaS and accept the access conditions.
2. Create a Hugging Face **read** token (Settings → Access Tokens).
3. In this Kaggle notebook: **Settings → Accelerator → GPU T4 x2** and **Internet → On** (needs a phone-verified Kaggle account).
4. **Add-ons → Secrets**: add `HF_TOKEN` (your token) and `UPSTREAM_KEY` (any long random string — the gateway will use it). Tick both for this notebook.

Then **Run All** and keep the tab open. The public URL prints in step 5.

_N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies._
"""),
md("## 1. Check GPUs and install server packages"),
code("""
!nvidia-smi --query-gpu=name,memory.total --format=csv
# Kaggle's preinstalled PyTorch is kept as-is. Installing vLLM upgrades PyTorch and breaks it on Kaggle.
!pip install -q fastapi uvicorn accelerate
"""),
md("## 2. Load secrets"),
code("""
import os, secrets
from kaggle_secrets import UserSecretsClient
_s = UserSecretsClient()
os.environ["HF_TOKEN"] = _s.get_secret("HF_TOKEN")
try:
    os.environ["UPSTREAM_KEY"] = _s.get_secret("UPSTREAM_KEY")
except Exception:
    os.environ["UPSTREAM_KEY"] = secrets.token_urlsafe(32)
    print("No UPSTREAM_KEY secret found; generated one for this session:", os.environ["UPSTREAM_KEY"])
print("Secrets loaded.")
"""),
md("""
## 3. Choose the server

T4s don't support bf16, so the model runs in fp16, split across both GPUs. First start downloads ~16 GB and takes 5–10 minutes.
"""),
code("""
import subprocess, time, requests

USE_FALLBACK = True  # transformers server (reliable on Kaggle). vLLM path needs `pip install vllm` and a matching PyTorch.

def start_vllm():
    cmd = [
        "vllm", "serve", "NCAIR1/N-ATLaS",
        "--served-model-name", "n-atlas",
        "--dtype", "half",
        "--tensor-parallel-size", "2",
        "--max-model-len", "8192",
        "--gpu-memory-utilization", "0.90",
        "--api-key", os.environ["UPSTREAM_KEY"],
        "--port", "8000",
    ]
    return subprocess.Popen(cmd, stdout=open("server.log", "w"), stderr=subprocess.STDOUT, env=os.environ.copy())

if not USE_FALLBACK:
    server = start_vllm()
    print("vLLM starting (pid", server.pid, ") — logs in server.log")
"""),
md("""
## 3b. transformers server (default)

Loads N-ATLaS in fp16 across both T4s and serves an OpenAI-compatible API on port 8000.
"""),
code("%%writefile fallback_server.py\n" + fallback),
code("""
if USE_FALLBACK:
    try: server.kill()
    except Exception: pass
    server = subprocess.Popen(["python", "fallback_server.py"], stdout=open("server.log", "w"), stderr=subprocess.STDOUT, env=os.environ.copy())
    print("Fallback server starting (pid", server.pid, ")")
"""),
md("## 4. Wait until the model is ready"),
code("""
deadline = time.time() + 25 * 60
while time.time() < deadline:
    if server.poll() is not None:
        print("Server exited. Last log lines:\\n")
        print("".join(open("server.log").readlines()[-40:]))
        raise SystemExit("Server crashed — switch to the fallback (step 3b).")
    try:
        if requests.get("http://localhost:8000/health", timeout=3).status_code == 200:
            print("N-ATLaS is up ✅"); break
    except Exception:
        pass
    time.sleep(15)
    print("...still loading", time.strftime("%H:%M:%S"), "|", (open("server.log").readlines() or [""])[-1].strip()[:120])
else:
    raise SystemExit("Timed out waiting for the server. Check server.log.")
"""),
md("## 5. Public URL (Cloudflare quick tunnel)"),
code("""
import re
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O cloudflared && chmod +x cloudflared
tunnel = subprocess.Popen(["./cloudflared", "tunnel", "--no-autoupdate", "--url", "http://localhost:8000"],
                          stdout=open("tunnel.log", "w"), stderr=subprocess.STDOUT)
PUBLIC_URL = None
for _ in range(60):
    m = re.search(r"https://[a-z0-9-]+\\.trycloudflare\\.com", open("tunnel.log").read())
    if m: PUBLIC_URL = m.group(0); break
    time.sleep(2)
print("UPSTREAM_URL =", PUBLIC_URL)
print("Set this as UPSTREAM_URL in the gateway (it changes every session).")
"""),
md("## 6. Smoke test through the public URL"),
code("""
time.sleep(5)
SYSTEM = "You are a friendly, helpful assistant. Reply in the same language the user writes in."
tests = {
    "Hausa": "Menene amfanin ruwa ga jikin dan Adam?",
    "Igbo": "Kedu ihe bụ uru mmiri na-arụ n'ahụ mmadụ?",
    "Yoruba": "Kini anfaani omi fun ara eniyan?",
    "English": "In two sentences, why is clean water important?",
}
for lang, q in tests.items():
    t0 = time.time()
    r = requests.post(f"{PUBLIC_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['UPSTREAM_KEY']}"},
        json={"model": "n-atlas", "messages": [{"role":"system","content":SYSTEM},{"role":"user","content":q}],
              "temperature": 0.1, "max_tokens": 200, "repetition_penalty": 1.12},
        timeout=300)
    r.raise_for_status()
    print(f"--- {lang} ({time.time()-t0:.1f}s)\\n{r.json()['choices'][0]['message']['content']}\\n")
"""),
md("## 7. Keep alive\nLeave this running while you test or record. Stop it to end the session."),
code("""
while True:
    alive = server.poll() is None and tunnel.poll() is None
    print(time.strftime("%H:%M:%S"), "server+tunnel up" if alive else "⚠️ something stopped — re-run steps 3–5", "|", PUBLIC_URL)
    time.sleep(120)
"""),
]
nb = {"cells":cells,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python"}},"nbformat":4,"nbformat_minor":5}
for c in nb["cells"]:
    src = c["source"]; lines = src.split("\n")
    c["source"] = [l+"\n" for l in lines[:-1]] + [lines[-1]]
json.dump(nb, open(out,"w"), indent=1, ensure_ascii=False)
