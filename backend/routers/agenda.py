from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import EventCreate
from utils.notify import notify_users

router = APIRouter(prefix="/agenda", tags=["agenda"])


@router.get("/events")
async def list_events(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    events = (
        db.from_("calendar_events").select("*, courses(title)").order("start_time").execute().data or []
    )
    return [
        {
            **{k: v for k, v in e.items() if k != "courses"},
            "course_title": (e.get("courses") or {}).get("title"),
        }
        for e in events
    ]


@router.post("/events")
async def create_event(
    body: EventCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Not authorized")
    res = db.from_("calendar_events").insert(
        {
            "title": body.title,
            "description": body.description,
            "start_time": body.start_time,
            "end_time": body.end_time,
            "event_type": body.event_type,
            "course_id": body.course_id,
            "created_by": user.id,
        }
    ).execute()
    new_event = res.data[0]

    # Notify all students (calendar_events has no class_id — broadcast to every student)
    try:
        student_rows = (
            db.from_("user_roles")
            .select("user_id")
            .eq("role", "student")
            .execute()
            .data or []
        )
        student_ids = [r["user_id"] for r in student_rows]
        notify_users(
            db,
            student_ids,
            f"Nouvel événement : {body.title}",
            None,
            "info",
            f"/dashboard/agenda?focus={new_event['id']}",
        )
    except Exception:
        pass  # notification failure must never break the main operation

    return new_event


@router.put("/events/{event_id}")
async def update_event(
    event_id: str,
    body: EventCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    event = db.from_("calendar_events").select("created_by").eq("id", event_id).execute().data
    if not event:
        raise HTTPException(404, "Not found")
    if not user.is_admin() and event[0]["created_by"] != user.id:
        raise HTTPException(403, "Not authorized")
    res = db.from_("calendar_events").update(
        {
            "title": body.title,
            "description": body.description,
            "start_time": body.start_time,
            "end_time": body.end_time,
            "event_type": body.event_type,
            "course_id": body.course_id,
        }
    ).eq("id", event_id).execute()
    return res.data[0]


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    event = db.from_("calendar_events").select("created_by").eq("id", event_id).execute().data
    if not event:
        raise HTTPException(404, "Not found")
    if not user.is_admin() and event[0]["created_by"] != user.id:
        raise HTTPException(403, "Not authorized")
    db.from_("calendar_events").delete().eq("id", event_id).execute()
    return {"ok": True}
