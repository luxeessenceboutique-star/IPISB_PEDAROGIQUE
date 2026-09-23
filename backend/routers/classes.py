from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import ClassCreate, ClassUpdate, FormationCreate, AddStudentRequest, TransferStudentRequest
from utils.notify import notify_users

router = APIRouter(prefix="/classes", tags=["classes"])


def _with_specialty(classes: list[dict], db: Client) -> list[dict]:
    specialty_ids = list({c["specialty_id"] for c in classes if c.get("specialty_id")})
    specialty_map: dict[str, str] = {}
    if specialty_ids:
        rows = db.from_("specialties").select("id, name").in_("id", specialty_ids).execute().data or []
        specialty_map = {r["id"]: r["name"] for r in rows}
    return [{**c, "specialty_name": specialty_map.get(c.get("specialty_id", ""))} for c in classes]


def _admin_ids(db: Client) -> list[str]:
    rows = db.from_("user_roles").select("user_id").eq("role", "admin").execute().data or []
    return list({r["user_id"] for r in rows if r.get("user_id")})


@router.get("/all")
async def list_all_classes(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """All classes — used by the course-assignment picker (any prof/admin can assign to any class).
    Le caissier y a accès en lecture pour sélectionner une promo lors d'une inscription."""
    if not (user.can_create() or user.is_cashier()):
        raise HTTPException(403, "Professor or admin only")
    return db.from_("classes").select("id, name").order("name").execute().data or []


# ── Catalogue des formations ────────────────────────────────────────────────
@router.get("/formations")
async def list_formations(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Catalogue des formations (programmes) — pour le sélecteur de création de classe."""
    if not (user.can_create() or user.is_cashier()):
        raise HTTPException(403, "Professor or admin only")
    return db.from_("formations").select(
        "id, name, code, default_duration_months, description"
    ).order("name").execute().data or []


@router.post("/formations")
async def create_formation(
    body: FormationCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Ajoute une formation au catalogue (création à la volée depuis le formulaire de classe)."""
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "Le nom de la formation est requis")
    if body.default_duration_months is not None and body.default_duration_months < 0:
        raise HTTPException(400, "default_duration_months doit être >= 0")
    res = db.from_("formations").insert({
        "name": name,
        "code": (body.code or "").strip() or None,
        "default_duration_months": body.default_duration_months,
        "description": (body.description or "").strip() or None,
        "created_by": user.id,
    }).execute()
    return res.data[0]


# ── Formateurs (comptes professeur) ─────────────────────────────────────────
@router.get("/trainers")
async def list_trainers(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Comptes formateurs (rôle professor) — pour le sélecteur de formateur."""
    if not (user.can_create() or user.is_cashier()):
        raise HTTPException(403, "Professor or admin only")
    roles = db.from_("user_roles").select("user_id").eq("role", "professor").execute().data or []
    ids = list({r["user_id"] for r in roles if r.get("user_id")})
    if not ids:
        return []
    profs = db.from_("profiles").select("id, full_name, email").in_("id", ids).execute().data or []
    profs.sort(key=lambda p: (p.get("full_name") or p.get("email") or "").lower())
    return profs


@router.get("")
async def list_classes(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not (user.can_create() or user.is_cashier()):
        raise HTTPException(403, "Professor or admin only")

    if user.is_admin() or user.is_cashier():
        classes = db.from_("classes").select("*").order("created_at", desc=True).execute().data or []
    else:
        classes = (
            db.from_("classes")
            .select("*")
            .eq("created_by", user.id)
            .order("created_at", desc=True)
            .execute()
            .data or []
        )

    all_memberships = db.from_("class_students").select("class_id").execute().data or []
    count_map: dict[str, int] = {}
    for m in all_memberships:
        count_map[m["class_id"]] = count_map.get(m["class_id"], 0) + 1

    # Noms : créateur + formateur (profiles) et libellés de formation (catalogue)
    people_ids = list({
        pid
        for c in classes
        for pid in (c.get("created_by"), c.get("trainer_id"))
        if pid
    })
    prof_map: dict[str, str] = {}
    if people_ids:
        profs = db.from_("profiles").select("id, full_name").in_("id", people_ids).execute().data or []
        prof_map = {p["id"]: p["full_name"] or "—" for p in profs}

    classes = _with_specialty(classes, db)

    formation_ids = list({c["formation_id"] for c in classes if c.get("formation_id")})
    formation_map: dict[str, dict] = {}
    if formation_ids:
        fms = db.from_("formations").select("id, name, code").in_("id", formation_ids).execute().data or []
        formation_map = {f["id"]: f for f in fms}

    return [
        {
            **c,
            "student_count": count_map.get(c["id"], 0),
            "professor_name": prof_map.get(c["created_by"], "—") if c.get("created_by") else "—",
            "trainer_name": prof_map.get(c["trainer_id"]) if c.get("trainer_id") else None,
            "formation_name": (formation_map.get(c["formation_id"]) or {}).get("name") if c.get("formation_id") else None,
            "formation_code": (formation_map.get(c["formation_id"]) or {}).get("code") if c.get("formation_id") else None,
        }
        for c in classes
    ]


def _schedule_from_period(start_date, duration_months) -> dict:
    """Aligne l'échéancier de paiement (Suivi scolarité) sur la période de formation :
    mois de départ = date de début, nb de mensualités = durée en mois."""
    out: dict = {}
    if start_date:
        s = str(start_date)[:10]
        if len(s) >= 7:
            out["payment_start_month"] = s[:7] + "-01"   # 1er du mois de début
    if duration_months is not None and duration_months >= 1:
        out["installments_count"] = min(24, int(duration_months))
    return out


def _validate_refs(db: Client, formation_id, trainer_id, duration_months) -> None:
    """Vérifie que la formation existe, que le formateur est bien un professeur, et la durée."""
    if duration_months is not None and duration_months < 0:
        raise HTTPException(400, "La durée (mois) doit être >= 0")
    if formation_id:
        f = db.from_("formations").select("id").eq("id", formation_id).execute().data
        if not f:
            raise HTTPException(400, "Formation introuvable")
    if trainer_id:
        r = (
            db.from_("user_roles").select("role")
            .eq("user_id", trainer_id).eq("role", "professor").execute().data
        )
        if not r:
            raise HTTPException(400, "Le formateur sélectionné n'est pas un compte professeur")


@router.post("")
async def create_class(
    body: ClassCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not (user.can_create() or user.is_cashier()):
        raise HTTPException(403, "Professor or admin only")
    _validate_refs(db, body.formation_id, body.trainer_id, body.duration_months)
    class_data = {
        "name": body.name,
        "description": body.description,
        "specialty_id": body.specialty_id,
        "year_number": body.year_number,
        "formation_id": body.formation_id,
        "trainer_id": body.trainer_id,
        "start_date": body.start_date,
        "duration_months": body.duration_months,
        "created_by": user.id,
        # L'échéancier de paiement suit la période de formation par défaut
        **_schedule_from_period(body.start_date, body.duration_months),
    }

    # Caissier : création soumise à validation N+1.
    if user.is_cashier() and not user.is_admin():
        op = db.from_("pending_operations").insert({
            "op_type": "class_create",
            "payload": class_data,
            "created_by": user.id,
        }).execute()
        op_id = op.data[0]["id"] if op.data else None
        notify_users(
            db, _admin_ids(db),
            title="Nouvelle classe à valider 🏫",
            message=f"Une classe « {body.name} » saisie par la caisse attend votre validation.",
            type="info",
            link=f"/dashboard/accounting?tab=validations&focus={op_id}",
        )
        return {"pending": True, "op_id": op_id}

    res = db.from_("classes").insert(class_data).execute()
    return _with_specialty(res.data, db)[0]


@router.patch("/{class_id}")
async def update_class(
    class_id: str,
    body: ClassUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    cls = db.from_("classes").select("created_by").eq("id", class_id).execute().data
    if not cls:
        raise HTTPException(404, "Classe introuvable")
    if not user.is_admin() and cls[0]["created_by"] != user.id:
        raise HTTPException(403, "Non autorisé")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Aucun champ à mettre à jour")
    _validate_refs(db, updates.get("formation_id"), updates.get("trainer_id"), updates.get("duration_months"))
    # Réaligne l'échéancier de paiement si la date de début / la durée changent
    if "start_date" in updates or "duration_months" in updates:
        updates.update(_schedule_from_period(updates.get("start_date"), updates.get("duration_months")))
    res = db.from_("classes").update(updates).eq("id", class_id).execute()
    if not res.data:
        raise HTTPException(404, "Classe introuvable")
    return _with_specialty(res.data, db)[0]


@router.delete("/{class_id}")
async def delete_class(
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    cls = db.from_("classes").select("created_by").eq("id", class_id).execute().data
    if not cls:
        raise HTTPException(404, "Classe introuvable")
    if not user.is_admin() and cls[0]["created_by"] != user.id:
        raise HTTPException(403, "Non autorisé")
    db.from_("class_students").delete().eq("class_id", class_id).execute()
    db.from_("classes").delete().eq("id", class_id).execute()
    return {"ok": True}


@router.get("/{class_id}/students")
async def get_class_students(
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    cls = db.from_("classes").select("created_by").eq("id", class_id).execute().data
    if not cls:
        raise HTTPException(404, "Classe introuvable")
    if not user.is_admin() and not user.is_cashier() and cls[0]["created_by"] != user.id:
        raise HTTPException(403, "Non autorisé")

    memberships = (
        db.from_("class_students")
        .select("student_id, added_at")
        .eq("class_id", class_id)
        .execute()
        .data or []
    )
    if not memberships:
        return []

    student_ids = [m["student_id"] for m in memberships]
    profiles = (
        db.from_("profiles")
        .select("id, email, full_name")
        .in_("id", student_ids)
        .execute()
        .data or []
    )
    added_map = {m["student_id"]: m["added_at"] for m in memberships}
    return [{**p, "added_at": added_map.get(p["id"])} for p in profiles]


@router.post("/{class_id}/students")
async def add_student(
    class_id: str,
    body: AddStudentRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    cls = db.from_("classes").select("created_by").eq("id", class_id).execute().data
    if not cls:
        raise HTTPException(404, "Classe introuvable")

    # ── Caissier / réceptionniste : validation N+1 ─────────────────────────
    # La saisie part en file d'attente et doit être validée par un admin.
    if user.is_cashier() and not user.is_admin():
        payload = {"class_id": class_id, "student_id": body.student_id}
        op = db.from_("pending_operations").insert({
            "op_type": "student_enrollment",
            "payload": payload,
            "class_id": class_id,
            "student_id": body.student_id,
            "created_by": user.id,
        }).execute()
        op_id = op.data[0]["id"] if op.data else None
        notify_users(
            db, _admin_ids(db),
            title="Nouvelle inscription à valider 🎓",
            message="Une inscription saisie par la caisse attend votre validation.",
            type="info",
            link=f"/dashboard/accounting?tab=validations&focus={op_id}",
        )
        return {"pending": True, "op_id": op_id}

    if not user.is_admin() and cls[0]["created_by"] != user.id:
        raise HTTPException(403, "Non autorisé")

    if not user.is_admin():
        student = (
            db.from_("profiles")
            .select("id")
            .eq("id", body.student_id)
            .eq("created_by", user.id)
            .execute()
            .data
        )
        if not student:
            raise HTTPException(403, "Cet étudiant ne fait pas partie de vos étudiants")

    try:
        db.from_("class_students").insert({
            "class_id": class_id,
            "student_id": body.student_id,
        }).execute()
    except Exception as e:
        raise HTTPException(400, str(e))

    return {"ok": True}


@router.post("/{class_id}/students/{student_id}/transfer")
async def transfer_student(
    class_id: str,
    student_id: str,
    body: TransferStudentRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Transfère un élève d'une classe à une autre de la MÊME filière (formation).
    Le changement de filière est refusé (les prix diffèrent). Caissier : validation N+1.
    """
    if not (user.is_admin() or user.is_cashier()):
        raise HTTPException(403, "Admin ou caissier uniquement")
    to_class_id = (body.to_class_id or "").strip()
    if not to_class_id:
        raise HTTPException(400, "Classe cible requise")
    if to_class_id == class_id:
        raise HTTPException(400, "L'élève est déjà dans cette classe")

    rows = db.from_("classes").select("id, name, formation_id").in_("id", [class_id, to_class_id]).execute().data or []
    by_id = {c["id"]: c for c in rows}
    if class_id not in by_id or to_class_id not in by_id:
        raise HTTPException(404, "Classe source ou cible introuvable")
    # Contrainte métier : même filière (formation) obligatoire.
    if by_id[class_id].get("formation_id") != by_id[to_class_id].get("formation_id"):
        raise HTTPException(400, "Transfert refusé : la classe cible appartient à une autre filière (prix différents)")

    enrolled = (
        db.from_("class_students").select("student_id")
        .eq("class_id", class_id).eq("student_id", student_id).execute().data
    )
    if not enrolled:
        raise HTTPException(404, "Élève non inscrit à la classe d'origine")

    # Caissier : validation N+1.
    if user.is_cashier() and not user.is_admin():
        op = db.from_("pending_operations").insert({
            "op_type": "student_transfer",
            "payload": {"student_id": student_id, "from_class_id": class_id, "to_class_id": to_class_id},
            "class_id": to_class_id,
            "student_id": student_id,
            "created_by": user.id,
        }).execute()
        op_id = op.data[0]["id"] if op.data else None
        notify_users(
            db, _admin_ids(db),
            title="Transfert d'élève à valider 🔁",
            message=f"Un transfert vers « {by_id[to_class_id]['name']} » attend votre validation.",
            type="info",
            link=f"/dashboard/accounting?tab=validations&focus={op_id}",
        )
        return {"pending": True, "op_id": op_id}

    upd = (
        db.from_("class_students").update({"class_id": to_class_id})
        .eq("class_id", class_id).eq("student_id", student_id).execute()
    )
    if not upd.data:
        raise HTTPException(404, "Élève non inscrit à la classe d'origine")
    return {"ok": True}


@router.delete("/{class_id}/students/{student_id}")
async def remove_student(
    class_id: str,
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    cls = db.from_("classes").select("created_by").eq("id", class_id).execute().data
    if not cls:
        raise HTTPException(404, "Classe introuvable")
    if not user.is_admin() and cls[0]["created_by"] != user.id:
        raise HTTPException(403, "Non autorisé")
    db.from_("class_students").delete().eq("class_id", class_id).eq("student_id", student_id).execute()
    return {"ok": True}
