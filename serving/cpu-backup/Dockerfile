# AtlasBridge CPU backup: N-ATLaS (Q4_K_M GGUF) served by llama.cpp on a free Hugging Face CPU Space.
# OpenAI-compatible API on port 7860. Set the Space secret LLAMA_API_KEY to require a bearer key.
FROM ghcr.io/ggml-org/llama.cpp:server

# Spaces run as a non-root user; keep the model download in a writable place.
ENV LLAMA_CACHE=/tmp/llama-cache
EXPOSE 7860

# -hf downloads tosinamuda/N-ATLaS-GGUF (quantised from NCAIR1/N-ATLaS) on first start (~4.9 GB).
# --jinja uses the chat template embedded in the GGUF (N-ATLaS / Llama-3 format).
CMD ["-hf", "tosinamuda/N-ATLaS-GGUF:Q4_K_M", \
     "--alias", "n-atlas", \
     "--host", "0.0.0.0", "--port", "7860", \
     "--ctx-size", "4096", "--n-predict", "256", \
     "--threads", "2", "--parallel", "1", \
     "--jinja"]
