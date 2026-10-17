from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from supabase import Client

from deps import get_current_user, get_db, CurrentUser
from models import ContinuousAssessmentGenerate, ContinuousAssessmentUpdate, AiEditRequest
from utils.audit import log_audit
from utils.controle_continu_generation import gather_course_content, generate_assessment_sections, edit_html_with_ai
from utils.controle_continu_docx import render_controle_continu_docx
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
    res = db.from_("continuous_assessments").insert(row).execute()
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

    res = db.from_("continuous_assessments").update(updates).eq("id", assessment_id).execute()
    log_audit(db, user.id, "continuous_assessment.update", "continuous_assessment", assessment_id,
              {k: v for k, v in updates.items() if k != "sections"})
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
    data = render_controle_continu_docx(payload)
    filename = safe_filename(f"Controle_continu_{assessment['title']}.docx")
    log_audit(db, user.id, "continuous_assessment.export", "continuous_assessment", assessment_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
