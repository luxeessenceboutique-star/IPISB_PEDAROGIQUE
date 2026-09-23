from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import AttendanceMark

router = APIRouter(tags=["attendance"])


def _check_schedule_access(db: Client, user: CurrentUser, schedule_id: str) -> dict:
    rows = db.from_("schedules").select("*").eq("id", schedule_id).execute().data
    if not rows:
        raise HTTPException(404, "Créneau introuvable")
    schedule = rows[0]
    if not user.is_admin() and schedule.get("created_by") != user.id and schedule.get("professor_id") != user.id:
        raise HTTPException(403, "Non autorisé")
    return schedule


@router.get("/schedules/{schedule_id}/seances")
async def get_or_create_seance(
    schedule_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    date: Optional[str] = Query(default=None),
):
    """Get (or lazily create) the séance for a schedule slot on a given date —
    defaults to today. A schedule row is a recurring pattern, not a dated
    instance, so this is where a specific occurrence actually gets a row."""
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    schedule = _check_schedule_access(db, user, schedule_id)
    seance_date = date or datetime.now(timezone.utc).date().isoformat()

    existing = (
        db.from_("seances").select("*")
        .eq("schedule_id", schedule_id).eq("date", seance_date)
        .execute().data
    )
    if existing:
        return existing[0]

    record = {
        "schedule_id": schedule_id,
        "class_id": schedule.get("class_id"),
        "course_id": schedule.get("course_id"),
        "date": seance_date,
        "created_by": user.id,
    }
    res = db.from_("seances").insert(record).execute()
    if not res.data:
        raise HTTPException(400, "Impossible de créer la séance")
    return res.data[0]


@router.get("/seances/{seance_id}/attendance")
async def get_attendance(
    seance_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    rows = db.from_("seances").select("*").eq("id", seance_id).execute().data
    if not rows:
        raise HTTPException(404, "Séance introuvable")
    seance = rows[0]
    _check_schedule_access(db, user, seance["schedule_id"])

    roster: list[dict] = []
    if seance.get("class_id"):
        memberships = (
            db.from_("class_students").select("student_id")
            .eq("class_id", seance["class_id"]).execute().data or []
        )
        student_ids = [m["student_id"] for m in memberships]
        if student_ids:
            roster = db.from_("profiles").select("id, full_name").in_("id", student_ids).order("full_name").execute().data or []

    marked = db.from_("attendance").select("student_id, status").eq("seance_id", seance_id).execute().data or []
    status_map = {m["student_id"]: m["status"] for m in marked}

    return {
        "seance": seance,
        "roster": [
            {"student_id": s["id"], "full_name": s["full_name"], "status": status_map.get(s["id"], "present")}
            for s in roster
        ],
    }


@router.post("/seances/{seance_id}/attendance")
async def mark_attendance(
    seance_id: str,
    body: AttendanceMark,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    rows = db.from_("seances").select("schedule_id").eq("id", seance_id).execute().data
    if not rows:
        raise HTTPException(404, "Séance introuvable")
    _check_schedule_access(db, user, rows[0]["schedule_id"])

    if not body.entries:
        raise HTTPException(400, "Aucune entrée à enregistrer")

    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"seance_id": seance_id, "student_id": e.student_id, "status": e.status, "marked_by": user.id, "marked_at": now}
        for e in body.entries
    ]
    res = db.from_("attendance").upsert(records, on_conflict="seance_id,student_id").execute()
    return res.data


@router.get("/students/{student_id}/attendance")
async def student_attendance_history(
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    rows = (
        db.from_("attendance")
        .select("status, marked_at, seances(date, course_id, class_id)")
        .eq("student_id", student_id)
        .order("marked_at", desc=True)
        .execute()
        .data or []
    )
    return rows
