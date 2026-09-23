from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import SpecialtyCreate, SpecialtyUpdate, SPECIALTY_TYPES
from utils.audit import log_audit

router = APIRouter(prefix="/specialties", tags=["specialties"])


@router.get("")
async def list_specialties(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    res = db.from_("specialties").select("*").order("name").execute()
    return res.data or []


def _require_admin(user: CurrentUser) -> None:
    if not user.is_admin():
        raise HTTPException(403, "Admin only")


@router.post("")
async def create_specialty(
    body: SpecialtyCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_admin(user)
    if not body.name.strip():
        raise HTTPException(400, "name is required")
    if body.type not in SPECIALTY_TYPES:
        raise HTTPException(400, f"type invalide (valeurs possibles : {', '.join(sorted(SPECIALTY_TYPES))})")

    res = db.from_("specialties").insert({"name": body.name, "type": body.type, "created_by": user.id}).execute()
    if not res.data:
        raise HTTPException(400, "Could not create specialty")

    specialty = res.data[0]
    log_audit(db, user.id, "specialty.create", "specialty", specialty["id"])
    return specialty


@router.patch("/{specialty_id}")
async def update_specialty(
    specialty_id: str,
    body: SpecialtyUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_admin(user)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    if "type" in updates and updates["type"] not in SPECIALTY_TYPES:
        raise HTTPException(400, f"type invalide (valeurs possibles : {', '.join(sorted(SPECIALTY_TYPES))})")

    res = db.from_("specialties").update(updates).eq("id", specialty_id).execute()
    if not res.data:
        raise HTTPException(404, "Not found")
    log_audit(db, user.id, "specialty.update", "specialty", specialty_id, updates)
    return res.data[0]


@router.delete("/{specialty_id}")
async def delete_specialty(
    specialty_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_admin(user)
    existing = db.from_("specialties").select("id").eq("id", specialty_id).execute().data
    if not existing:
        raise HTTPException(404, "Not found")

    db.from_("specialties").delete().eq("id", specialty_id).execute()
    log_audit(db, user.id, "specialty.delete", "specialty", specialty_id)
    return {"ok": True}
