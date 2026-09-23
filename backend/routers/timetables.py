from datetime import datetime, time, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from typing import Annotated, Optional
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import TimetableCreate, TimetableSlotCreate, TimetableSlotUpdate
from utils.audit import log_audit
from utils.pdf_generators import render_timetable_pdf

router = APIRouter(prefix="/timetables", tags=["timetables"])


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time() if len(value) <= 5 else time.fromisoformat(value)


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and b_start < a_end


def _find_conflicts(
    db: Client,
    room: str | None,
    professor_id: str | None,
    day_of_week: int,
    start_time: str,
    end_time: str,
    exclude_slot_id: str | None = None,
) -> list[dict]:
    """Room/instructor conflict check across ALL timetables (any class/week) —
    a professor or room can't be double-booked on the same weekday+time-of-day
    even across different classes' timetables."""
    start = _parse_time(start_time)
    end = _parse_time(end_time)

    candidates: list[dict] = []
    seen_ids: set[str] = set()
    if room:
        rows = db.from_("timetable_slots").select("*").eq("room", room).eq("day_of_week", day_of_week).execute().data or []
        for r in rows:
            if r["id"] not in seen_ids:
                candidates.append(r)
                seen_ids.add(r["id"])
    if professor_id:
        rows = db.from_("timetable_slots").select("*").eq("professor_id", professor_id).eq("day_of_week", day_of_week).execute().data or []
        for r in rows:
            if r["id"] not in seen_ids:
                candidates.append(r)
                seen_ids.add(r["id"])

    conflicts = []
    for c in candidates:
        if exclude_slot_id and c["id"] == exclude_slot_id:
            continue
        c_start = _parse_time(c["start_time"])
        c_end = _parse_time(c["end_time"])
        if _overlaps(start, end, c_start, c_end):
            conflicts.append(c)
    return conflicts


def _get_timetable_or_404(db: Client, timetable_id: str) -> dict:
    rows = db.from_("timetables").select("*, classes(name, created_by)").eq("id", timetable_id).execute().data
    if not rows:
        raise HTTPException(404, "Emploi du temps introuvable")
    return rows[0]


def _check_owner(user: CurrentUser, timetable: dict) -> None:
    class_created_by = (timetable.get("classes") or {}).get("created_by")
    if not user.is_admin() and class_created_by != user.id:
        raise HTTPException(403, "Non autorisé")


@router.get("")
async def list_timetables(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    class_id: Optional[str] = None,
    week_start: Optional[str] = None,
):
    query = db.from_("timetables").select("*, classes(name, created_by)")
    if class_id:
        query = query.eq("class_id", class_id)
    if week_start:
        query = query.eq("week_start", week_start)
    rows = query.order("week_start", desc=True).execute().data or []

    if not user.is_admin():
        rows = [r for r in rows if (r.get("classes") or {}).get("created_by") == user.id]

    return [
        {**{k: v for k, v in r.items() if k != "classes"}, "class_name": (r.get("classes") or {}).get("name")}
        for r in rows
    ]


@router.get("/rooms/usage")
async def get_rooms_usage(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Occupation réelle des salles — dérivée de l'emploi du temps validé le
    plus récent de chaque classe — enrichie de la fiche salle (capacité,
    bâtiment, équipement) quand elle existe (table `rooms`, mise en
    correspondance par nom) et des filières qui l'utilisent."""
    if not user.is_admin():
        raise HTTPException(403, "Admin only")

    timetables = (
        db.from_("timetables").select("id, class_id, week_start, status, classes(name, specialty_id)")
        .eq("status", "validated").order("week_start", desc=True)
        .execute().data or []
    )
    latest_by_class: dict[str, dict] = {}
    for t in timetables:
        if t["class_id"] not in latest_by_class:
            latest_by_class[t["class_id"]] = t
    timetable_ids = [t["id"] for t in latest_by_class.values()]

    specialty_ids = list({
        (t.get("classes") or {}).get("specialty_id")
        for t in latest_by_class.values() if (t.get("classes") or {}).get("specialty_id")
    })
    specialty_map = {
        s["id"]: s["name"]
        for s in (db.from_("specialties").select("id, name").in_("id", specialty_ids).execute().data or [])
    } if specialty_ids else {}

    slots = []
    if timetable_ids:
        slots = (
            db.from_("timetable_slots").select("*")
            .in_("timetable_id", timetable_ids).not_.is_("room", "null")
            .order("day_of_week").order("start_time")
            .execute().data or []
        )
    tt_map = {t["id"]: t for t in latest_by_class.values()}
    prof_ids = list({s["professor_id"] for s in slots if s.get("professor_id")})
    prof_map = {p["id"]: p["full_name"] for p in (db.from_("profiles").select("id, full_name").in_("id", prof_ids).execute().data or [])} if prof_ids else {}

    room_occ: dict[str, list[dict]] = {}
    room_filieres: dict[str, set[str]] = {}
    for s in slots:
        room = (s.get("room") or "").strip()
        if not room:
            continue
        tt = tt_map.get(s["timetable_id"], {})
        cls = tt.get("classes") or {}
        filiere = specialty_map.get(cls.get("specialty_id"))
        room_occ.setdefault(room, []).append({
            "day_of_week": s["day_of_week"],
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "subject": s.get("subject"),
            "class_name": cls.get("name"),
            "filiere": filiere,
            "professor_name": prof_map.get(s.get("professor_id")),
        })
        if filiere:
            room_filieres.setdefault(room, set()).add(filiere)

    # Fiches salles (table `rooms`) — mise en correspondance par nom
    # normalisé, pour rattacher capacité/bâtiment/équipement quand connus,
    # et faire apparaître les salles enregistrées sans occupation actuelle.
    room_records = db.from_("rooms").select("*").execute().data or []
    record_by_norm = {(r["name"] or "").strip().casefold(): r for r in room_records}

    all_names = set(room_occ.keys()) | {r["name"] for r in room_records}

    out = []
    for room in sorted(all_names, key=lambda n: n.casefold()):
        record = record_by_norm.get(room.strip().casefold())
        occ = room_occ.get(room, [])
        out.append({
            "room": room,
            "room_id": record.get("id") if record else None,
            "capacity": record.get("capacity") if record else None,
            "building": record.get("building") if record else None,
            "floor": record.get("floor") if record else None,
            "equipment": record.get("equipment") if record else None,
            "notes": record.get("notes") if record else None,
            "filieres": sorted(room_filieres.get(room, set())),
            "slot_count": len(occ),
            "slots": occ,
        })
    return out


@router.get("/{timetable_id}")
async def get_timetable(
    timetable_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    timetable = _get_timetable_or_404(db, timetable_id)
    _check_owner(user, timetable)
    slots = (
        db.from_("timetable_slots")
        .select("*")
        .eq("timetable_id", timetable_id)
        .order("day_of_week")
        .order("start_time")
        .execute()
        .data or []
    )
    class_info = timetable.pop("classes", None) or {}
    return {**timetable, "class_name": class_info.get("name"), "slots": slots}


@router.post("")
async def create_timetable(
    body: TimetableCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")

    cls = db.from_("classes").select("created_by").eq("id", body.class_id).execute().data
    if not cls:
        raise HTTPException(404, "Classe introuvable")
    if not user.is_admin() and cls[0]["created_by"] != user.id:
        raise HTTPException(403, "Non autorisé")

    try:
        res = db.from_("timetables").insert({
            "class_id": body.class_id,
            "academic_year": body.academic_year,
            "week_start": body.week_start,
            "week_end": body.week_end,
            "created_by": user.id,
        }).execute()
    except Exception as e:
        raise HTTPException(400, f"Un emploi du temps existe déjà pour cette classe et cette semaine ({e})")

    new_timetable = res.data[0]
    log_audit(db, user.id, "timetable.create", "timetable", new_timetable["id"])
    return new_timetable


@router.post("/{timetable_id}/slots")
async def create_slot(
    timetable_id: str,
    body: TimetableSlotCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    timetable = _get_timetable_or_404(db, timetable_id)
    _check_owner(user, timetable)
    if timetable["status"] == "validated":
        raise HTTPException(403, "Emploi du temps validé — déverrouillez-le avant de le modifier")

    conflicts = _find_conflicts(db, body.room, body.professor_id, body.day_of_week, body.start_time, body.end_time)
    if conflicts:
        raise HTTPException(409, {"message": "Conflit de salle/formateur détecté", "conflicts": conflicts})

    res = db.from_("timetable_slots").insert({
        "timetable_id": timetable_id,
        "day_of_week": body.day_of_week,
        "start_time": body.start_time,
        "end_time": body.end_time,
        "subject": body.subject,
        "slot_type": body.slot_type,
        "professor_id": body.professor_id,
        "room": body.room,
    }).execute()
    new_slot = res.data[0]
    log_audit(db, user.id, "timetable.slot.create", "timetable_slot", new_slot["id"])
    return new_slot


@router.put("/{timetable_id}/slots/{slot_id}")
async def update_slot(
    timetable_id: str,
    slot_id: str,
    body: TimetableSlotUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    timetable = _get_timetable_or_404(db, timetable_id)
    _check_owner(user, timetable)
    if timetable["status"] == "validated":
        raise HTTPException(403, "Emploi du temps validé — déverrouillez-le avant de le modifier")

    existing = db.from_("timetable_slots").select("*").eq("id", slot_id).eq("timetable_id", timetable_id).execute().data
    if not existing:
        raise HTTPException(404, "Créneau introuvable")
    current = existing[0]
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    merged = {**current, **updates}

    conflicts = _find_conflicts(
        db, merged.get("room"), merged.get("professor_id"), merged["day_of_week"],
        merged["start_time"], merged["end_time"], exclude_slot_id=slot_id,
    )
    if conflicts:
        raise HTTPException(409, {"message": "Conflit de salle/formateur détecté", "conflicts": conflicts})

    res = db.from_("timetable_slots").update(updates).eq("id", slot_id).execute()
    log_audit(db, user.id, "timetable.slot.update", "timetable_slot", slot_id, updates)
    return res.data[0]


@router.delete("/{timetable_id}/slots/{slot_id}")
async def delete_slot(
    timetable_id: str,
    slot_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    timetable = _get_timetable_or_404(db, timetable_id)
    _check_owner(user, timetable)
    if timetable["status"] == "validated":
        raise HTTPException(403, "Emploi du temps validé — déverrouillez-le avant de le modifier")

    db.from_("timetable_slots").delete().eq("id", slot_id).eq("timetable_id", timetable_id).execute()
    log_audit(db, user.id, "timetable.slot.delete", "timetable_slot", slot_id)
    return {"ok": True}


@router.post("/{timetable_id}/validate")
async def validate_timetable(
    timetable_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    timetable = _get_timetable_or_404(db, timetable_id)
    _check_owner(user, timetable)
    if timetable["status"] == "validated":
        raise HTTPException(400, "Déjà validé")

    slots = db.from_("timetable_slots").select("*").eq("timetable_id", timetable_id).execute().data or []
    for s in slots:
        conflicts = _find_conflicts(
            db, s.get("room"), s.get("professor_id"), s["day_of_week"], s["start_time"], s["end_time"],
            exclude_slot_id=s["id"],
        )
        if conflicts:
            raise HTTPException(409, {"message": "Conflit de salle/formateur détecté — corrigez avant de valider", "conflicts": conflicts})

    res = db.from_("timetables").update({
        "status": "validated",
        "validated_by": user.id,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", timetable_id).execute()
    log_audit(db, user.id, "timetable.validate", "timetable", timetable_id)
    return res.data[0]


@router.post("/{timetable_id}/unlock")
async def unlock_timetable(
    timetable_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    timetable = _get_timetable_or_404(db, timetable_id)
    _check_owner(user, timetable)

    res = db.from_("timetables").update({
        "status": "draft",
        "validated_by": None,
        "validated_at": None,
    }).eq("id", timetable_id).execute()
    log_audit(db, user.id, "timetable.unlock", "timetable", timetable_id)
    return res.data[0]


@router.get("/{timetable_id}/pdf")
async def download_timetable_pdf(
    timetable_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    timetable = _get_timetable_or_404(db, timetable_id)
    _check_owner(user, timetable)
    if timetable["status"] != "validated":
        raise HTTPException(403, "Validez l'emploi du temps avant de le télécharger")

    slots = (
        db.from_("timetable_slots")
        .select("*")
        .eq("timetable_id", timetable_id)
        .order("day_of_week")
        .order("start_time")
        .execute()
        .data or []
    )

    prof_ids = list({s["professor_id"] for s in slots if s.get("professor_id")})
    prof_map: dict[str, str] = {}
    if prof_ids:
        profs = db.from_("profiles").select("id, full_name").in_("id", prof_ids).execute().data or []
        prof_map = {p["id"]: p["full_name"] or "—" for p in profs}
    for s in slots:
        s["professor_name"] = prof_map.get(s.get("professor_id"), None)

    class_name = (timetable.get("classes") or {}).get("name") or "—"
    pdf_bytes = render_timetable_pdf(timetable, slots, class_name)

    filename = f"EDT_{class_name}_{timetable['week_start']}.pdf".replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
