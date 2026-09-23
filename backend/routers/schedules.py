from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, Optional
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import ScheduleCreate, ScheduleUpdate
from utils.audit import log_audit
from utils.dt import parse_iso_dt

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _find_conflicts(
    db: Client,
    room: str,
    professor_id: str | None,
    start_time: str,
    end_time: str,
    exclude_id: str | None = None,
) -> list[dict]:
    """Room/instructor conflict check. Recurring ('weekly') slots are compared
    by weekday + time-of-day only, since a fixed institute timetable repeats
    indefinitely; 'once' slots are compared on the exact calendar window."""
    start = parse_iso_dt(start_time)
    end = parse_iso_dt(end_time)

    candidates = db.from_("schedules").select("*").eq("room", room).execute().data or []
    if professor_id:
        prof_rows = db.from_("schedules").select("*").eq("professor_id", professor_id).execute().data or []
        seen_ids = {c["id"] for c in candidates}
        candidates += [r for r in prof_rows if r["id"] not in seen_ids]

    conflicts = []
    for c in candidates:
        if exclude_id and c["id"] == exclude_id:
            continue
        c_start = parse_iso_dt(c["start_time"])
        c_end = parse_iso_dt(c["end_time"])

        if c.get("recurrence") == "weekly" or start.date() != c_start.date():
            # Compare weekday + time-of-day only
            if start.weekday() != c_start.weekday():
                continue
            same_day = start.date()
            norm_start = datetime.combine(same_day, start.timetz())
            norm_end = datetime.combine(same_day, end.timetz())
            c_norm_start = datetime.combine(same_day, c_start.timetz())
            c_norm_end = datetime.combine(same_day, c_end.timetz())
            if _overlaps(norm_start, norm_end, c_norm_start, c_norm_end):
                conflicts.append(c)
        else:
            if _overlaps(start, end, c_start, c_end):
                conflicts.append(c)

    return conflicts


@router.get("")
async def list_schedules(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    class_id: Optional[str] = None,
    professor_id: Optional[str] = None,
    room: Optional[str] = None,
):
    query = db.from_("schedules").select("*, classes(name)")
    if class_id:
        query = query.eq("class_id", class_id)
    if professor_id:
        query = query.eq("professor_id", professor_id)
    if room:
        query = query.eq("room", room)
    rows = query.order("start_time").execute().data or []
    return [
        {**{k: v for k, v in r.items() if k != "classes"}, "class_name": (r.get("classes") or {}).get("name")}
        for r in rows
    ]


@router.post("")
async def create_schedule(
    body: ScheduleCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")

    conflicts = _find_conflicts(db, body.room, body.professor_id, body.start_time, body.end_time)
    if conflicts:
        raise HTTPException(409, {"message": "Room/instructor conflict detected", "conflicts": conflicts})

    res = db.from_("schedules").insert({
        "class_id": body.class_id,
        "professor_id": body.professor_id,
        "room": body.room,
        "title": body.title,
        "start_time": body.start_time,
        "end_time": body.end_time,
        "recurrence": body.recurrence,
        "created_by": user.id,
    }).execute()
    new_schedule = res.data[0]
    log_audit(db, user.id, "schedule.create", "schedule", new_schedule["id"])
    return new_schedule


@router.put("/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    body: ScheduleUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")

    existing = db.from_("schedules").select("*").eq("id", schedule_id).execute().data
    if not existing:
        raise HTTPException(404, "Not found")
    current = existing[0]

    merged = {**current, **{k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}}

    conflicts = _find_conflicts(
        db, merged["room"], merged.get("professor_id"), merged["start_time"], merged["end_time"], exclude_id=schedule_id
    )
    if conflicts:
        raise HTTPException(409, {"message": "Room/instructor conflict detected", "conflicts": conflicts})

    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    res = db.from_("schedules").update(updates).eq("id", schedule_id).execute()
    log_audit(db, user.id, "schedule.update", "schedule", schedule_id, updates)
    return res.data[0]


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    db.from_("schedules").delete().eq("id", schedule_id).execute()
    log_audit(db, user.id, "schedule.delete", "schedule", schedule_id)
    return {"ok": True}
