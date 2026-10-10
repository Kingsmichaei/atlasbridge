"""
AtlasBridge fallback server.

A minimal OpenAI-compatible server for N-ATLaS using Hugging Face transformers.
Use this only if vLLM fails to start on the GPU. It is slower (one request at a
time) but works on almost any CUDA GPU, including Kaggle's 2x T4.

Endpoints:
  GET  /health
  GET  /v1/models
  POST /v1/chat/completions   (supports "stream": true)

Env:
  HF_TOKEN       Hugging Face token with access to NCAIR1/N-ATLaS
  UPSTREAM_KEY   Bearer key callers must send (optional but recommended)
  PORT           default 8000
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

MODEL_ID = "NCAIR1/N-ATLaS"
SERVED_NAME = "n-atlas"
HF_TOKEN = os.environ.get("HF_TOKEN")
API_KEY = os.environ.get("UPSTREAM_KEY", "")

print("Loading tokenizer...", flush=True)
tok = AutoTokenizer.from_pretrained(MODEL_ID, token=HF_TOKEN)
print("Loading model (fp16, split across available GPUs)...", flush=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    device_map="auto",
    token=HF_TOKEN,
)
model.eval()

EOS_IDS = [tok.eos_token_id]
_eot = tok.convert_tokens_to_ids("<|eot_id|>")
if isinstance(_eot, int) and _eot not in EOS_IDS:
    EOS_IDS.append(_eot)

gen_lock = threading.Lock()  # one generation at a time
app = FastAPI(title="AtlasBridge fallback (N-ATLaS)")


def check_auth(request: Request) -> None:
    if API_KEY and request.headers.get("authorization") != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid upstream key")


def prepare(body: dict):
    messages = body.get("messages")
    if not messages:
        raise HTTPException(status_code=400, detail="'messages' is required")
    text = tok.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
        date_string=datetime.now().strftime("%d %b %Y"),
    )
    inputs = tok(text, return_tensors="pt", add_special_tokens=False).to("cuda:0")
    temperature = float(body.get("temperature", 0.1))
    max_tokens = int(body.get("max_tokens") or 512)
    kwargs = dict(
        max_new_tokens=max_tokens,
        repetition_penalty=float(body.get("repetition_penalty", 1.12)),
        do_sample=temperature > 0,
        use_cache=True,
        eos_token_id=EOS_IDS,
        pad_token_id=tok.eos_token_id,
    )
    if temperature > 0:
        kwargs.update(temperature=temperature, top_p=float(body.get("top_p", 0.9)))
    return inputs, kwargs, max_tokens


@app.get("/health")
def health():
    return {"status": "ok", "model": SERVED_NAME}


@app.get("/v1/models")
def models(request: Request):
    check_auth(request)
    return {"object": "list", "data": [{"id": SERVED_NAME, "object": "model", "owned_by": "awarri"}]}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    check_auth(request)
    body = await request.json()
    inputs, kwargs, max_tokens = prepare(body)
    prompt_tokens = int(inputs["input_ids"].shape[1])
    cid = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if body.get("stream"):
        streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)

        def run():
            with gen_lock, torch.inference_mode():
                model.generate(**inputs, **kwargs, streamer=streamer)

        threading.Thread(target=run, daemon=True).start()

        def chunk(delta, finish=None):
            payload = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": created,
                "model": SERVED_NAME,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        def events():
            yield chunk({"role": "assistant"})
            for piece in streamer:
                if piece:
                    yield chunk({"content": piece})
            yield chunk({}, "stop")
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    with gen_lock, torch.inference_mode():
        out = model.generate(**inputs, **kwargs)
    new_tokens = out[0][prompt_tokens:]
    text = tok.decode(new_tokens, skip_special_tokens=True).strip()
    completion_tokens = int(new_tokens.shape[0])
    return {
        "id": cid,
        "object": "chat.completion",
        "created": created,
        "model": SERVED_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "length" if completion_tokens >= max_tokens else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
