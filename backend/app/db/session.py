from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker  # noqa: F401 — sessionmaker used by tests

from app.config import BACKEND_ROOT, get_settings
from app.db.models import Base


def resolve_database_url(database_url: str) -> str:
    """Make SQLite paths absolute under the backend package so cwd does not matter."""
    if not database_url.startswith("sqlite:///"):
        return database_url

    raw = database_url.removeprefix("sqlite:///")
    if raw == ":memory:":
        return database_url

    path = Path(raw)
    if not path.is_absolute():
        path = (BACKEND_ROOT / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def create_db_engine() -> Engine:
    settings = get_settings()
    database_url = resolve_database_url(settings.database_url)

    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        future=True,
    )

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _ensure_column(table: str, column: str, ddl_type: str) -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    if engine.url.get_backend_name() == "sqlite":
        _ensure_column("workspaces", "logo_data_url", "TEXT")
        _ensure_column("workspaces", "favicon_data_url", "TEXT")
        _ensure_column("workspaces", "accent_color", "VARCHAR(32) DEFAULT '#0f6e56'")
        _ensure_column("workspaces", "retention_days_paid", "INTEGER DEFAULT 365")
        _ensure_column("workspaces", "retention_keep_audit", "BOOLEAN DEFAULT 1")
        _ensure_column("users", "role", "VARCHAR(32) DEFAULT 'owner'")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
