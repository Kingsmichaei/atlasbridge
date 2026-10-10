"""AtlasBridge: a small Python client for N-ATLaS, Nigeria's multilingual LLM.

    from atlasbridge import AtlasBridge
    ab = AtlasBridge(api_key="ab_...", base_url="https://<your-gateway>/v1")
    print(ab.chat("Kedu ka ị mere?"))

N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and
Digital Economy, and powered by Awarri Technologies.
"""

from .client import AtlasBridge, AtlasBridgeError, Conversation

__all__ = ["AtlasBridge", "AtlasBridgeError", "Conversation"]
__version__ = "0.1.0"
