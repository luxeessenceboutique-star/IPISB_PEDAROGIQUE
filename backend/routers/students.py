from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, Optional
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import StudentDetailsUpdate, StudentUpdate
from utils.audit import log_audit

router = APIRouter(prefix="/students", tags=["students"])


def _student_role_ids(db: Client) -> set[str]:
    rows = db.from_("user_roles").select("user_id").eq("role", "student").execute().data or []
    return {r["user_id"] for r in rows}


@router.get("")
async def list_students(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    q: Optional[str] = None,
    statut: Optional[str] = None,
    class_id: Optional[str] = None,
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")

    student_ids = _student_role_ids(db)
    if not student_ids:
        return []

    query = db.from_("profiles").select("id, email, full_name, statut, photo_url, created_at").in_(
        "id", list(student_ids)
    )
    if not user.is_admin():
        query = query.eq("created_by", user.id)
    if statut:
        query = query.eq("statut", statut)
    if q:
        # pg_trgm-backed ilike search on name/email — <150ms at institute scale
        query = query.or_(f"full_name.ilike.%{q}%,email.ilike.%{q}%")

    profiles = query.order("full_name").execute().data or []

    if class_id:
        members = (
            db.from_("class_students").select("student_id").eq("class_id", class_id).execute().data or []
        )
        member_ids = {m["student_id"] for m in members}
        profiles = [p for p in profiles if p["id"] in member_ids]

    return profiles


@router.get("/{student_id}")
async def get_student(
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")

    rows = (
        db.from_("profiles")
        .select("id, email, full_name, statut, photo_url, created_at, created_by")
        .eq("id", student_id)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(404, "Not found")
    profile = rows[0]
    if not user.is_admin() and profile.get("created_by") != user.id:
        raise HTTPException(403, "Not authorized")

    classes = (
        db.from_("class_students")
        .select("classes(id, name)")
        .eq("student_id", student_id)
        .execute()
        .data or []
    )
    profile["classes"] = [c["classes"] for c in classes if c.get("classes")]

    details = db.from_("student_details").select("*").eq("student_id", student_id).execute().data
    profile["details"] = details[0] if details else None
    return profile


@router.patch("/{student_id}/details")
async def update_student_details(
    student_id: str,
    body: StudentDetailsUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.is_admin():
        raise HTTPException(403, "Admin only")
    exists = db.from_("profiles").select("id").eq("id", student_id).execute().data
    if not exists:
        raise HTTPException(404, "Not found")

    # Empty string means "clear this field" — store NULL, not "".
    updates = {k: (v.strip() or None if isinstance(v, str) else v)
               for k, v in body.model_dump(exclude_unset=True).items()}
    if not updates:
        raise HTTPException(400, "No fields to update")

    row = {
        "student_id": student_id,
        **updates,
        "updated_by": user.id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = db.from_("student_details").upsert(row).execute()
    except Exception as e:
        raise HTTPException(400, f"Mise à jour impossible : {str(e)}")

    log_audit(db, user.id, "student.details_update", "student", student_id, updates)
    return res.data[0]


@router.patch("/{student_id}")
async def update_student(
    student_id: str,
    body: StudentUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.is_admin():
        raise HTTPException(403, "Admin only")

    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    res = db.from_("profiles").update(updates).eq("id", student_id).execute()
    if not res.data:
        raise HTTPException(404, "Not found")

    log_audit(db, user.id, "student.update", "student", student_id, updates)
    return res.data[0]
