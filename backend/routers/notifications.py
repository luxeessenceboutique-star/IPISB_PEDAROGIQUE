from fastapi import APIRouter, Depends
from typing import Annotated
from supabase import Client
from deps import get_current_user, get_db, CurrentUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    return (
        db.from_("notifications")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
        .data or []
    )


@router.put("/read-all")
async def mark_all_read(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    db.from_("notifications").update({"read": True}).eq("user_id", user.id).eq("read", False).execute()
    return {"ok": True}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    db.from_("notifications").update({"read": True}).eq("id", notification_id).eq("user_id", user.id).execute()
    return {"ok": True}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    db.from_("notifications").delete().eq("id", notification_id).eq("user_id", user.id).execute()
    return {"ok": True}
