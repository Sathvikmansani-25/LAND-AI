"""SQLAlchemy engine/session setup (PostgreSQL via psycopg v3 in production;
falls back to a local SQLite file only if no DATABASE_URL is configured at
all -- see app/config.py). This replaces the old sqlite3-based app/db.py.
"""
import datetime as dt

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# pool_pre_ping guards against Neon (or any managed Postgres) silently
# closing idle connections -- a stale connection is detected and replaced
# instead of surfacing as a confusing "server closed the connection
# unexpectedly" error on the next request.
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a Session per-request and always closes it,
    mirroring the old Flask `g.db` + teardown_appcontext lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind=None) -> None:
    """Creates any missing tables. Safe to call repeatedly (CREATE TABLE IF
    NOT EXISTS semantics) -- app/seed.py passes the direct/unpooled engine,
    since DDL is best run outside a transaction-pooled connection."""
    from app import models  # noqa: F401 -- ensures all model classes are registered on Base.metadata

    Base.metadata.create_all(bind=bind or engine)


def reset_schema(bind=None) -> None:
    """Drops and recreates every table -- used by the seed script to start
    from a clean slate, same as the old sqlite reset_schema(). Pass the
    unpooled engine (see unpooled_engine()) so DDL doesn't run through a
    transaction-mode pooler."""
    from app import models  # noqa: F401

    target = bind or engine
    Base.metadata.drop_all(bind=target)
    Base.metadata.create_all(bind=target)


def now_iso() -> str:
    return dt.datetime.utcnow().isoformat()


def unpooled_engine():
    """A separate engine bound to the direct/unpooled connection string, for
    schema creation and bulk-insert scripts (app/seed.py) that shouldn't run
    through a transaction-mode pooler like Neon's PgBouncer."""
    if settings.database_url_unpooled == settings.database_url:
        return engine
    connect_args = {"check_same_thread": False} if settings.database_url_unpooled.startswith("sqlite") else {}
    return create_engine(settings.database_url_unpooled, pool_pre_ping=True, connect_args=connect_args)


def healthcheck() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 -- health endpoint reports False, doesn't crash
        return False
