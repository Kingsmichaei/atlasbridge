"""Runtime settings, all read from environment variables."""

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Where N-ATLaS is served (the Kaggle tunnel URL, or any OpenAI-compatible server).
    upstream_url: str = field(default_factory=lambda: os.environ.get("UPSTREAM_URL", "").rstrip("/"))
    upstream_key: str = field(default_factory=lambda: os.environ.get("UPSTREAM_KEY", ""))
    upstream_model: str = field(default_factory=lambda: os.environ.get("UPSTREAM_MODEL", "n-atlas"))
    upstream_timeout: float = field(default_factory=lambda: float(os.environ.get("UPSTREAM_TIMEOUT", "300")))
    # Return canned replies instead of calling the model (local development / CI).
    mock_upstream: bool = field(default_factory=lambda: _bool("MOCK_UPSTREAM"))

    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./atlasbridge.db"))
    admin_token: str = field(default_factory=lambda: os.environ.get("ADMIN_TOKEN", ""))
    # Beta testers sign up with this code to get a key. Empty = self-serve signup disabled.
    signup_code: str = field(default_factory=lambda: os.environ.get("SIGNUP_CODE", ""))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.environ.get("RATE_LIMIT_PER_MINUTE", "20")))
    # Store a short preview of prompts/replies in usage logs (off by default for privacy).
    log_content: bool = field(default_factory=lambda: _bool("LOG_CONTENT"))
    cors_origins: list[str] = field(
        default_factory=lambda: [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
    )


settings = Settings()

ATTRIBUTION = (
    "N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and "
    "Digital Economy, and powered by Awarri Technologies."
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a friendly, helpful assistant built on N-ATLaS, a Nigerian language model. "
    "You understand English, Hausa, Igbo and Yoruba. Keep answers clear and concise."
)
