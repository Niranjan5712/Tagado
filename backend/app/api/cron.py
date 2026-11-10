from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.services.scheduler import tick

router = APIRouter(tags=["cron"])


@router.post("/cron/tick")
def cron_tick(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_cron_secret: str | None = Header(default=None),
) -> dict:
    if not x_cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")
    return tick(db, settings=settings)
