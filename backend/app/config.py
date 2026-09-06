import os
from pydantic import BaseModel


def _load_dotenv_simple(path: str) -> None:
    """Tiny zero-dependency ".env" loader (only sets a var if not already set
    in the real environment). Local/dev convenience only -- on Vercel, env
    vars come from the project's configured Environment Variables instead,
    and this is a harmless no-op there since there's no committed .env file."""
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        pass


_load_dotenv_simple(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


def _normalize_database_url(raw: str) -> str:
    """Most Postgres hosts (Neon included) hand out "postgres://" or plain
    "postgresql://" connection strings, but this app uses psycopg (v3) as
    its driver (see requirements.txt) -- SQLAlchemy needs that spelled out
    as "postgresql+psycopg://", or it defaults to looking for psycopg2
    instead. Normalize so a connection string copy-pasted from Neon/Vercel
    works without the caller having to think about any of this."""
    if not raw:
        return raw
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://"):]
    return raw


def _default_database_url() -> str:
    """Prefer the pooled connection string (DATABASE_URL, routed through
    PgBouncer on Neon) for normal request-time use -- this is what the
    deployed FastAPI app should use, since a serverless function can spin up
    many concurrent short-lived connections and pooling keeps that cheap.
    Fall back to the unpooled/direct URL if that's the only one set (e.g. a
    plain "install Postgres yourself" setup that only defines one string),
    and finally to a local SQLite file so the app still boots for a quick
    local smoke-test with zero setup (this is NOT a supported production
    path -- see README's Vercel/Neon deployment section)."""
    url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("POSTGRES_URL")
    if url:
        return _normalize_database_url(url)
    local_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "landguard.db")
    return f"sqlite:///{local_db_path}"


_DATABASE_URL = _default_database_url()
_DATABASE_URL_UNPOOLED = (
    _normalize_database_url(
        os.getenv("DATABASE_URL_UNPOOLED") or os.getenv("POSTGRES_URL_NON_POOLING", "")
    )
    or _DATABASE_URL
)


class Settings(BaseModel):
    # Plain BaseModel, not pydantic_settings.BaseSettings, on purpose: every
    # field below already reads its own env var explicitly via os.getenv(...)
    # in its default expression (so a normalized/derived value -- like the
    # postgresql+psycopg:// URL built by _normalize_database_url -- can differ
    # from the raw env var). BaseSettings would auto-bind each field to its
    # same-named env var and silently override these computed defaults with
    # the RAW env var value, undoing exactly that normalization -- which is
    # exactly what caused SQLAlchemy to pick the psycopg2 dialect instead of
    # psycopg (v3) once a real DATABASE_URL was set (Neon/Vercel).
    app_name: str = "LandGuard AI"

    # Normal request-time database connection (pooled, if available). See
    # README's "Deploying to Vercel" section for how DATABASE_URL /
    # DATABASE_URL_UNPOOLED get populated by the Neon Postgres integration.
    database_url: str = _DATABASE_URL
    # Direct/unpooled connection, used for schema creation and one-off admin
    # scripts (app/seed.py) -- DDL and bulk inserts behave more predictably
    # outside a transaction-mode connection pooler than the pooled URL does.
    # Falls back to database_url itself if no separate unpooled URL is set.
    database_url_unpooled: str = _DATABASE_URL_UNPOOLED

    secret_key: str = os.getenv("SECRET_KEY", "landguard-dev-secret-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]

    # risk tier thresholds (probability of delay, 0-1)
    risk_medium_threshold: float = 0.40
    risk_high_threshold: float = 0.70

    model_dir: str = os.path.join(os.path.dirname(__file__), "ml", "artifacts")

    # --- LandBot AI (optional real-LLM upgrade) ---------------------------
    # If GROQ_API_KEY is set (real env var, or in a backend/.env file), the
    # chatbot uses a real hosted LLM (via Groq's free/low-cost OpenAI-compatible
    # API) with function-calling against the live database, so it can answer
    # arbitrary questions instead of only the hand-coded intents. With no key
    # set, or if any API call fails, it automatically falls back to the
    # offline rule-based chatbot (app/chatbot.py) -- the app never breaks.
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    # openai/gpt-oss-120b is Groq-hosted; swap for e.g. "qwen/qwen3-32b" or
    # "openai/gpt-oss-20b" (smaller/cheaper/faster) via GROQ_MODEL if you like.
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    # Optional: "low" / "medium" / "high" -- only meaningful for gpt-oss
    # models. Leave unset to use the model's default.
    groq_reasoning_effort: str = os.getenv("GROQ_REASONING_EFFORT", "")
    llm_chatbot_enabled: bool = os.getenv("LLM_CHATBOT_ENABLED", "true").strip().lower() not in ("0", "false", "no")


settings = Settings()
