from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from deps import get_current_user, get_db, CurrentUser
from utils.login_approval import approve_login_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]):
    """Called right after sign-in — its only real job is to run the
    get_current_user login-approval gate before the app navigates into
    the dashboard. 403 here means the account is pending approval."""
    return {"id": user.id, "email": user.email, "roles": user.roles}


@router.post("/login-approvals/{token}/approve")
async def approve_login(token: str, db: Annotated[Client, Depends(get_db)]):
    """Public — no auth. Hit by the one-click link in the approval email."""
    ok = approve_login_token(db, token)
    if not ok:
        raise HTTPException(410, "Ce lien est invalide, déjà utilisé, ou expiré.")
    return {"ok": True}
