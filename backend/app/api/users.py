from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace
from app.db.models import User, Workspace
from app.db.session import get_db
from app.services.security import hash_password

router = APIRouter(tags=["users"])

ROLES = ("owner", "operator", "viewer")


class WorkspaceUserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(default="operator")


class UpdateUserRoleRequest(BaseModel):
    role: str


def _require_owner(user: User) -> None:
    role = getattr(user, "role", None) or "owner"
    if role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can manage users",
        )


@router.get("/users")
def list_users(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    users = list(db.scalars(select(User).where(User.workspace_id == workspace.id).order_by(User.name)))
    return {
        "users": [
            WorkspaceUserOut(
                id=user.id,
                email=user.email,
                name=user.name,
                role=getattr(user, "role", None) or "owner",
            ).model_dump()
            for user in users
        ],
        "roles": [
            {"id": "owner", "label": "Owner", "description": "Full access, including users and settings"},
            {
                "id": "operator",
                "label": "Operator",
                "description": "Approve reminders, confirm payments, resolve issues",
            },
            {"id": "viewer", "label": "Viewer", "description": "Read-only access to invoices and clients"},
        ],
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    actor: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _require_owner(actor)
    role = payload.role.strip().lower()
    if role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role")
    if role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create operators or viewers here. Ownership stays with existing owners.",
        )

    email = str(payload.email).strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email is already in use")

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        role=role,
        workspace_id=workspace.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return WorkspaceUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
    ).model_dump()


@router.patch("/users/{user_id}")
def update_user_role(
    user_id: str,
    payload: UpdateUserRoleRequest,
    actor: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _require_owner(actor)
    role = payload.role.strip().lower()
    if role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role")

    user = db.scalar(select(User).where(User.id == user_id, User.workspace_id == workspace.id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == actor.id and role != "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own owner role",
        )

    user.role = role
    db.commit()
    db.refresh(user)
    return WorkspaceUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
    ).model_dump()


@router.delete("/users/{user_id}")
def remove_user(
    user_id: str,
    actor: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _require_owner(actor)
    if user_id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove yourself")

    user = db.scalar(select(User).where(User.id == user_id, User.workspace_id == workspace.id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    owners = list(
        db.scalars(select(User).where(User.workspace_id == workspace.id, User.role == "owner"))
    )
    if (getattr(user, "role", None) or "owner") == "owner" and len(owners) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keep at least one owner on the workspace",
        )

    db.delete(user)
    db.commit()
    return {"status": "ok"}
