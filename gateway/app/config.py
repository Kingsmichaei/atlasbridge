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
    # Always-on CPU backup (llama.cpp serving the N-ATLaS Q4_K_M GGUF), used when the GPU server is down.
    fallback_url: str = field(default_factory=lambda: os.environ.get("UPSTREAM_FALLBACK_URL", "").rstrip("/"))
    fallback_key: str = field(default_factory=lambda: os.environ.get("UPSTREAM_FALLBACK_KEY", ""))
    fallback_max_tokens: int = field(default_factory=lambda: int(os.environ.get("FALLBACK_MAX_TOKENS", "256")))
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

    # Developer accounts (website + dashboard).
    # Signs the session cookie. Empty = a random secret per process, so sessions end on restart.
    session_secret: str = field(default_factory=lambda: os.environ.get("SESSION_SECRET", ""))
    session_days: int = field(default_factory=lambda: int(os.environ.get("SESSION_DAYS", "14")))
    # Always mark the session cookie Secure. Needed behind a TLS-terminating proxy such as Render's.
    session_cookie_secure: bool = field(default_factory=lambda: _bool("SESSION_COOKIE_SECURE"))
    # /auth/signup asks for SIGNUP_CODE while this is on and SIGNUP_CODE is set.
    account_signup_require_code: bool = field(default_factory=lambda: _bool("ACCOUNT_SIGNUP_REQUIRE_CODE", True))
    max_keys_per_user: int = field(default_factory=lambda: int(os.environ.get("MAX_KEYS_PER_USER", "5")))
    # Login and signup attempts allowed per client IP in any 15 minutes (each counted separately).
    auth_attempts_per_15_min: int = field(default_factory=lambda: int(os.environ.get("AUTH_ATTEMPTS_PER_15_MIN", "10")))


settings = Settings()

ATTRIBUTION = (
    "N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and "
    "Digital Economy, and powered by Awarri Technologies."
)

DEFAULT_SYSTEM_PROMPT = (
    "You are N-ATLaS, a multilingual language model developed by Awarri Technologies as an initiative "
    "of the Federal Ministry of Communications, Innovation and Digital Economy of Nigeria, served through "
    "AtlasBridge. You were not made by OpenAI, Google, Meta or any other company; if asked who made you or "
    "what model you are, say this. You understand English, Hausa, Igbo and Yoruba. "
    "Be friendly and helpful, and keep answers clear and concise."
)
