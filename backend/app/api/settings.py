from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace
from app.config import Settings, get_settings
from app.db.models import Workspace
from app.db.session import get_db
from app.services.security import generate_mcp_token
from app.services.seed import reset_demo_workspace
from app.services.serialize import serialize_workspace_settings

router = APIRouter(tags=["settings"])


class SettingsPatch(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=200)
    sender_name: str | None = Field(default=None, min_length=1, max_length=200)
    reply_to_email: EmailStr | None = None
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    ifsc: str | None = None
    upi_id: str | None = None
    udyam_number: str | None = None
    send_hour_ist: int | None = Field(default=None, ge=9, le=19)
    send_minute_ist: int | None = Field(default=None, ge=0, le=59)
    logo_data_url: str | None = None
    favicon_data_url: str | None = None
    accent_color: str | None = Field(default=None, min_length=4, max_length=32)
    retention_days_paid: int | None = Field(default=None, ge=30, le=3650)
    retention_keep_audit: bool | None = None


@router.get("/settings")
def get_settings_route(
    workspace: Workspace = Depends(get_current_workspace),
    settings: Settings = Depends(get_settings),
) -> dict:
    return serialize_workspace_settings(workspace, settings)


@router.patch("/settings")
def patch_settings(
    payload: SettingsPatch,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(workspace, key, value)
    db.commit()
    db.refresh(workspace)
    return serialize_workspace_settings(workspace, settings)


@router.post("/settings/regenerate-claude-link")
def regenerate_claude_link(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    workspace.mcp_token = generate_mcp_token()
    db.commit()
    db.refresh(workspace)
    return serialize_workspace_settings(workspace, settings)


@router.post("/demo/reset")
def reset_demo(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not workspace.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sample data reset is only available on the review workspace",
        )
    reset_demo_workspace(db, workspace, settings)
    db.refresh(workspace)
    return {
        "status": "ok",
        "summary": "Sample data restored.",
        "settings": serialize_workspace_settings(workspace, settings),
    }
