"""Salles — fiches réelles (capacité, bâtiment/étage, équipement) gérées par
l'admin. Distinct de `timetable_slots.room` (texte libre sur chaque créneau) :
la mise en correspondance par nom se fait dans
GET /api/timetables/rooms/usage (backend/routers/timetables.py)."""
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from deps import CurrentUser, get_current_user, get_db
from models import RoomCreate, RoomUpdate
from utils.audit import log_audit

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _require_admin(user: CurrentUser) -> None:
    if not user.is_admin():
        raise HTTPException(403, "Admin only")


@router.get("")
async def list_rooms(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not (user.is_admin() or user.is_prof()):
        raise HTTPException(403, "Admin or professor only")
    return db.from_("rooms").select("*").order("name").execute().data or []


@router.post("")
async def create_room(
    body: RoomCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_admin(user)
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Le nom de la salle est requis")
    existing = db.from_("rooms").select("id").ilike("name", name).execute().data
    if existing:
        raise HTTPException(400, "Une salle porte déjà ce nom")
    row = body.model_dump()
    row["name"] = name
    row["created_by"] = user.id
    res = db.from_("rooms").insert(row).execute()
    log_audit(db, user.id, "room.create", "room", res.data[0]["id"])
    return res.data[0]


@router.patch("/{room_id}")
async def update_room(
    room_id: str,
    body: RoomUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_admin(user)
    existing = db.from_("rooms").select("id").eq("id", room_id).execute().data
    if not existing:
        raise HTTPException(404, "Salle introuvable")
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        updates["name"] = (updates["name"] or "").strip()
        if not updates["name"]:
            raise HTTPException(400, "Le nom de la salle est requis")
    if not updates:
        raise HTTPException(400, "Aucun champ à mettre à jour")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = db.from_("rooms").update(updates).eq("id", room_id).execute()
    log_audit(db, user.id, "room.update", "room", room_id, updates)
    return res.data[0]


@router.delete("/{room_id}")
async def delete_room(
    room_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_admin(user)
    existing = db.from_("rooms").select("id").eq("id", room_id).execute().data
    if not existing:
        raise HTTPException(404, "Salle introuvable")
    db.from_("rooms").delete().eq("id", room_id).execute()
    log_audit(db, user.id, "room.delete", "room", room_id)
    return {"ok": True}
