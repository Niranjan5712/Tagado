from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db import session as db_session
from app.db.models import Base, Workspace
from app.services.security import generate_mcp_token, hash_password
from app.db.models import User


@pytest.fixture()
def db(tmp_path, monkeypatch) -> Generator[Session, None, None]:
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("DEMO_EMAIL", "owner@pixelcraft.test")
    monkeypatch.setenv("DEMO_PASSWORD", "test-password-123")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    get_settings.cache_clear()

    db_session.engine = db_session.create_db_engine()
    db_session.SessionLocal = db_session.sessionmaker(
        bind=db_session.engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    Base.metadata.create_all(bind=db_session.engine)

    session = db_session.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=db_session.engine)
        get_settings.cache_clear()


@pytest.fixture()
def workspace(db: Session) -> Workspace:
    settings = get_settings()
    ws = Workspace(
        business_name=settings.demo_business_name,
        sender_name=f"{settings.demo_owner_name} at {settings.demo_business_name}",
        reply_to_email=settings.demo_email,
        bank_account_name=settings.demo_business_name,
        bank_account_number="50200011223344",
        ifsc="HDFC0001234",
        upi_id="pixelcraft@hdfcbank",
        udyam_number="UDYAM-TN-02-0123456",
        mcp_token=generate_mcp_token(),
        is_demo=True,
    )
    db.add(ws)
    db.flush()
    db.add(
        User(
            email=settings.demo_email,
            password_hash=hash_password(settings.demo_password),
            name=settings.demo_owner_name,
            workspace_id=ws.id,
        )
    )
    db.commit()
    db.refresh(ws)
    return ws
