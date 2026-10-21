"""Database models: developer accounts, API keys and usage logs (SQLite locally, Postgres in production)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """A developer account on the website. Beta keys made before v2.2.0 have no user."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)  # always lowercase
    name: Mapped[str] = mapped_column(String(120))
    organisation: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))  # argon2id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    """A logged-in browser. The cookie holds a random token; only its SHA-256 is stored."""
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), default="")
    organisation: Mapped[str] = mapped_column(String(200), default="")
    prefix: Mapped[str] = mapped_column(String(16), index=True)  # first chars, safe to show
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    # Added in v2.2.0 (see _migrate). All nullable so existing beta keys keep working unchanged.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    label: Mapped[str] = mapped_column(String(60), default="")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Deleted keys are revoked and hidden from the dashboard, but the row stays for usage history.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_id: Mapped[int | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(60))
    language: Mapped[str] = mapped_column(String(16), default="")
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float] = mapped_column(Float)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    streamed: Mapped[bool] = mapped_column(Boolean, default=False)
    client: Mapped[str] = mapped_column(String(120), default="")  # User-Agent, e.g. "atlasbridge-python/0.1"
    prompt_preview: Mapped[str] = mapped_column(Text, default="")
    reply_preview: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    backend: Mapped[str] = mapped_column(String(20), default="")  # "gpu", "cpu-backup", "mock"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


def _engine_url(url: str) -> str:
    # Render/Neon give "postgres://"; SQLAlchemy wants "postgresql+psycopg://".
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_url = _engine_url(settings.database_url)
engine = create_engine(
    _url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    """Add columns introduced after v2.0.0 to existing databases (create_all doesn't alter tables)."""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(engine).get_columns("usage_logs")}
    if "backend" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE usage_logs ADD COLUMN backend VARCHAR(20) DEFAULT ''"))

    # v2.2.0: developer accounts. The users and user_sessions tables come from create_all above.
    for sql in migration_sql(set(c["name"] for c in inspect(engine).get_columns("api_keys"))):
        with engine.begin() as conn:
            conn.execute(text(sql))


def migration_sql(api_key_cols: set[str], dialect: str | None = None) -> list[str]:
    """The ALTER statements v2.2.0 needs on an api_keys table that has the given columns."""
    ts = "TIMESTAMP WITH TIME ZONE" if (dialect or engine.dialect.name) == "postgresql" else "DATETIME"
    wanted = {
        "user_id": "INTEGER REFERENCES users(id)",
        "label": "VARCHAR(60) DEFAULT ''",
        "last_used_at": ts,
        "revoked_at": ts,
        "deleted_at": ts,
    }
    out = [f"ALTER TABLE api_keys ADD COLUMN {name} {ddl}" for name, ddl in wanted.items() if name not in api_key_cols]
    if "user_id" not in api_key_cols:
        out.append("CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys (user_id)")
    return out
