from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from supabase import Client

from deps import get_current_user, get_db, CurrentUser
from models import (
    ContinuousAssessmentGenerate, ContinuousAssessmentUpdate, AiEditRequest,
    ContinuousAssessmentGradesUpsert,
)
from utils.audit import log_audit
from utils.controle_continu_generation import gather_course_content, generate_assessment_sections, edit_html_with_ai
from utils.controle_continu_docx import render_controle_continu_docx
from utils.examen_docx import render_examen_docx
from utils.safe_filename import safe_filename

router = APIRouter(prefix="/continuous-assessments", tags=["continuous-assessments"])


def _require_creator(user: CurrentUser) -> None:
    if not user.can_create():
        raise HTTPException(403, "Réservé aux formateurs et administrateurs")


def _load_owned(db: Client, assessment_id: str, user: CurrentUser) -> dict:
    rows = db.from_("continuous_assessments").select("*").eq("id", assessment_id).execute().data
    if not rows:
        raise HTTPException(404, "Contrôle continu introuvable")
    assessment = rows[0]
    if not user.is_admin() and assessment.get("created_by") != user.id:
        raise HTTPException(403, "Non autorisé — ce n'est pas votre contrôle continu")
    return assessment


def _fr_date(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


@router.get("")
async def list_continuous_assessments(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_creator(user)
    query = db.from_("continuous_assessments").select("*").order("created_at", desc=True)
    if not user.is_admin():
        query = query.eq("created_by", user.id)
    rows = query.execute().data or []
    return [{**r, "sections": None, "section_count": len(r.get("sections") or [])} for r in rows]


@router.get("/{assessment_id}")
async def get_continuous_assessment(
    assessment_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_creator(user)
    return _load_owned(db, assessment_id, user)


@router.post("/generate")
async def generate_continuous_assessment(
    body: ContinuousAssessmentGenerate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_creator(user)
    if not body.course_ids:
        raise HTTPException(400, "Sélectionnez au moins un cours")
    if body.doc_type not in ("controle_continu", "examen"):
        raise HTTPException(400, "doc_type invalide")

    courses = db.from_("courses").select("id, professor_id").in_("id", body.course_ids).execute().data or []
    if len(courses) != len(set(body.course_ids)):
        raise HTTPException(404, "Un ou plusieurs cours sélectionnés sont introuvables")
    if not user.is_admin():
        not_owned = [c["id"] for c in courses if c.get("professor_id") != user.id]
        if not_owned:
            raise HTTPException(403, "Non autorisé — un ou plusieurs cours sélectionnés ne vous appartiennent pas")

    content = gather_course_content(db, body.course_ids)
    try:
        sections = generate_assessment_sections(
            content, body.filiere, body.niveau, body.total_points, body.instructions,
        )
    except ValueError as e:
        raise HTTPException(502, str(e))

    row = {
        "title": body.title,
        "course_ids": body.course_ids,
        "filiere": body.filiere,
        "niveau": body.niveau,
        "formateur": body.formateur,
        "date_evaluation": body.date_evaluation,
        "duree_epreuve": body.duree_epreuve,
        "total_points": body.total_points,
        "sections": sections,
        "status": "draft",
        "created_by": user.id,
    }
    # doc_type/jury/pratique_sections (L66) — omis si la migration n'est pas
    # encore appliquée, pour ne pas casser la génération d'un Contrôle
    # continu classique (déjà en production) en attendant.
    if body.doc_type != "controle_continu" or body.jury or body.pratique_sections:
        row["doc_type"] = body.doc_type
        row["jury"] = [j.model_dump() for j in body.jury] if body.jury else []
        row["pratique_sections"] = [s.model_dump() for s in body.pratique_sections] if body.pratique_sections else []
    try:
        res = db.from_("continuous_assessments").insert(row).execute()
    except Exception as e:
        msg = str(e)
        if ("doc_type" in row or "jury" in row or "pratique_sections" in row) and ("Could not find" in msg or "schema cache" in msg):
            row.pop("doc_type", None)
            row.pop("jury", None)
            row.pop("pratique_sections", None)
            res = db.from_("continuous_assessments").insert(row).execute()
        else:
            raise
    new_assessment = res.data[0]
    log_audit(db, user.id, "continuous_assessment.generate", "continuous_assessment", new_assessment["id"],
              {"course_ids": body.course_ids, "section_count": len(sections)})
    return new_assessment


@router.patch("/{assessment_id}")
async def update_continuous_assessment(
    assessment_id: str,
    body: ContinuousAssessmentUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_creator(user)
    _load_owned(db, assessment_id, user)
    updates = body.model_dump(exclude_unset=True, exclude_none=True)
    if "sections" in updates:
        updates["sections"] = [s if isinstance(s, dict) else s for s in updates["sections"]]
    if "status" in updates and updates["status"] not in ("draft", "published"):
        raise HTTPException(400, "status invalide")
    if not updates:
        raise HTTPException(400, "Aucun champ à mettre à jour")

    try:
        res = db.from_("continuous_assessments").update(updates).eq("id", assessment_id).execute()
    except Exception as e:
        msg = str(e)
        new_cols = {"doc_type", "jury", "pratique_sections"} & updates.keys()
        if new_cols and ("Could not find" in msg or "schema cache" in msg):
            for k in new_cols:
                updates.pop(k, None)
            if not updates:
                raise HTTPException(400, "La migration L66 n'est pas encore appliquée — impossible de modifier ce champ pour l'instant.")
            res = db.from_("continuous_assessments").update(updates).eq("id", assessment_id).execute()
        else:
            raise
    log_audit(db, user.id, "continuous_assessment.update", "continuous_assessment", assessment_id,
              {k: v for k, v in updates.items() if k not in ("sections", "pratique_sections")})
    return res.data[0]


@router.delete("/{assessment_id}")
async def delete_continuous_assessment(
    assessment_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_creator(user)
    _load_owned(db, assessment_id, user)
    db.from_("continuous_assessments").delete().eq("id", assessment_id).execute()
    log_audit(db, user.id, "continuous_assessment.delete", "continuous_assessment", assessment_id)
    return {"ok": True}


@router.post("/ai-edit")
async def ai_edit_block(
    body: AiEditRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Réécrit UN bloc (consigne ou corrigé) selon une instruction libre —
    appelé pendant l'édition, avant sauvegarde (PATCH séparé)."""
    _require_creator(user)
    if not body.instruction.strip():
        raise HTTPException(400, "Instruction requise")
    try:
        html = edit_html_with_ai(body.html, body.instruction)
    except ValueError as e:
        raise HTTPException(502, str(e))
    return {"html": html}


@router.get("/{assessment_id}/grades")
async def get_assessment_grades(
    assessment_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Roster + notes EFCF déjà saisies pour un Examen — résout la classe
    via le 1er cours ciblé par l'Examen (en pratique un Examen cible un
    seul cours, cf. le gabarit) → class_courses → class_students, même
    cheminement que compute_overall_average."""
    _require_creator(user)
    assessment = _load_owned(db, assessment_id, user)
    if assessment.get("doc_type") != "examen":
        raise HTTPException(400, "La saisie des notes n'est disponible que pour un Examen")

    course_ids = assessment.get("course_ids") or []
    has_pratique = bool(assessment.get("pratique_sections"))
    if not course_ids:
        return {"students": [], "has_pratique": has_pratique}

    class_rows = db.from_("class_courses").select("class_id").eq("course_id", course_ids[0]).execute().data or []
    class_ids = list({r["class_id"] for r in class_rows})
    if not class_ids:
        return {"students": [], "has_pratique": has_pratique}

    memberships = db.from_("class_students").select("student_id").in_("class_id", class_ids).execute().data or []
    student_ids = list({m["student_id"] for m in memberships})
    if not student_ids:
        return {"students": [], "has_pratique": has_pratique}

    profiles = db.from_("profiles").select("id, email, full_name").in_("id", student_ids).execute().data or []
    try:
        grade_rows = (
            db.from_("continuous_assessment_grades").select("student_id, theorique_score, pratique_score")
            .eq("assessment_id", assessment_id).execute().data or []
        )
    except Exception:
        grade_rows = []  # L67 pas encore appliquée — liste d'élèves non notés plutôt qu'une erreur
    grade_map = {g["student_id"]: g for g in grade_rows}

    students = [{
        "id": p["id"], "full_name": p.get("full_name"), "email": p.get("email"),
        "theorique_score": grade_map.get(p["id"], {}).get("theorique_score"),
        "pratique_score": grade_map.get(p["id"], {}).get("pratique_score"),
    } for p in profiles]
    students.sort(key=lambda s: (s["full_name"] or s["email"] or "").lower())
    return {"students": students, "has_pratique": has_pratique}


@router.put("/{assessment_id}/grades")
async def set_assessment_grades(
    assessment_id: str,
    body: ContinuousAssessmentGradesUpsert,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_creator(user)
    assessment = _load_owned(db, assessment_id, user)
    if assessment.get("doc_type") != "examen":
        raise HTTPException(400, "La saisie des notes n'est disponible que pour un Examen")
    if not body.grades:
        return {"ok": True}

    existing = (
        db.from_("continuous_assessment_grades").select("id, student_id")
        .eq("assessment_id", assessment_id).in_("student_id", list(body.grades.keys()))
        .execute().data or []
    )
    by_student = {r["student_id"]: r["id"] for r in existing}
    to_insert = []
    for student_id, entry in body.grades.items():
        payload = {"theorique_score": entry.theorique_score, "pratique_score": entry.pratique_score, "graded_by": user.id}
        if student_id in by_student:
            db.from_("continuous_assessment_grades").update(payload).eq("id", by_student[student_id]).execute()
        else:
            to_insert.append({"assessment_id": assessment_id, "student_id": student_id, **payload})
    if to_insert:
        db.from_("continuous_assessment_grades").insert(to_insert).execute()
    log_audit(db, user.id, "continuous_assessment.grades_update", "continuous_assessment", assessment_id,
              {"count": len(body.grades)})
    return {"ok": True}


@router.get("/{assessment_id}/export.docx")
async def export_continuous_assessment_docx(
    assessment_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_creator(user)
    assessment = _load_owned(db, assessment_id, user)
    payload = {
        **assessment,
        "date_evaluation": _fr_date(assessment.get("date_evaluation")),
    }
    if assessment.get("doc_type") == "examen":
        data = render_examen_docx(payload)
        filename = safe_filename(f"Examen_{assessment['title']}.docx")
    else:
        data = render_controle_continu_docx(payload)
        filename = safe_filename(f"Controle_continu_{assessment['title']}.docx")
    log_audit(db, user.id, "continuous_assessment.export", "continuous_assessment", assessment_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
