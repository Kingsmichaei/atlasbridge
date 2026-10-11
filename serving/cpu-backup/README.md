---
title: AtlasBridge N-ATLaS CPU Backup
emoji: 🌍
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# AtlasBridge: N-ATLaS CPU backup

An always-on, CPU-only N-ATLaS server for [AtlasBridge](https://github.com/Kingsmichaei/atlasbridge). It serves `tosinamuda/N-ATLaS-GGUF` (Q4_K_M, a 4-bit quantisation of `NCAIR1/N-ATLaS`) with llama.cpp's OpenAI-compatible server.

The AtlasBridge gateway uses the fast GPU server when it's online and switches to this backup automatically when it isn't. Replies are slower here (roughly 2–5 tokens per second on 2 vCPUs), so the gateway caps backup replies at 256 tokens.

**Endpoints:** `GET /health`, `POST /v1/chat/completions` (Bearer `LLAMA_API_KEY`).

N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies. Use is subject to the N-ATLaS Terms of Use.
