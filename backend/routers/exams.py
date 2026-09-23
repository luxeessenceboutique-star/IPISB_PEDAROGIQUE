import os
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from supabase import Client

from deps import get_current_user, get_db, CurrentUser
from models import (
    ExamCreate, ExamUpdate, QuestionCreate, QuestionUpdate, QuestionsReorder,
    ExamAnswers, GenerateQuestionsRequest,
)
from utils.notify import notify_users
from utils.email import send_email
from utils.exam_generation import generate_mcq_questions
from utils.audit import log_audit
from utils.safe_filename import safe_filename
from utils.dt import parse_iso_dt

router = APIRouter(prefix="/exams", tags=["exams"])

# Same bucket course_generation.py already writes lesson images to — exam
# question images live alongside them, no new storage mechanism.
MATERIALS_BUCKET = "course-materials"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
IMAGE_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp")

# Network-latency cushion applied on top of duration_minutes when the
# backend authoritatively checks whether a submission arrived in time —
# the frontend auto-submits the instant its countdown hits zero, so a
# legitimate submission should never be more than a few seconds late.
SUBMIT_GRACE_SECONDS = 120


# ────────────────────────── ownership / authorization ──────────────────────
# Mirrors course_generation.py's _get_course_or_404/_require_owner pattern.
# Before this, create/delete/publish/question-CRUD only checked
# user.can_create() (any professor or admin) — never that the professor
# actually owned the exam's course, so any professor could manage any
# other professor's exam. Every mutating endpoint below now goes through
# _load_owned_exam (or _require_course_owner for course-scoped actions).

def _get_exam_or_404(db: Client, exam_id: str) -> dict:
    rows = db.from_("exams").select("*").eq("id", exam_id).execute().data
    if not rows:
        raise HTTPException(404, "Examen introuvable")
    return rows[0]


def _get_course_or_404(db: Client, course_id: str) -> dict:
    rows = db.from_("courses").select("*").eq("id", course_id).execute().data
    if not rows:
        raise HTTPException(404, "Cours introuvable")
    return rows[0]


def _require_course_owner(user: CurrentUser, course: dict) -> None:
    if not user.is_admin() and course.get("professor_id") != user.id:
        raise HTTPException(403, "Non autorisé — ce n'est pas votre cours")


def _load_owned_exam(db: Client, exam_id: str, user: CurrentUser) -> tuple[dict, dict]:
    exam = _get_exam_or_404(db, exam_id)
    course = _get_course_or_404(db, exam["course_id"])
    _require_course_owner(user, course)
    return exam, course


def _has_submissions(db: Client, exam_id: str) -> bool:
    rows = db.from_("exam_responses").select("id").eq("exam_id", exam_id).limit(1).execute().data
    return bool(rows)


def _ensure_editable(db: Client, exam_id: str) -> None:
    """§7/§23 — once a student has a response row (started or submitted),
    the exam they were given must stay reproducible. Blocks question CRUD
    and exam-content edits; publish/unpublish is unaffected since it
    doesn't rewrite history. Minimum viable protection, not full
    versioning — a professor who needs to change a live exam creates a
    new one instead."""
    if _has_submissions(db, exam_id):
        raise HTTPException(
            409,
            "Cet examen a déjà des réponses d'étudiants — il ne peut plus être modifié. "
            "Créez un nouvel examen pour une nouvelle version.",
        )


def _public_materials_url(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{MATERIALS_BUCKET}/{path}"


def _parse_dt(value: str) -> datetime:
    return parse_iso_dt(value)


def _with_image_url(q: dict) -> dict:
    if q.get("image_path"):
        q = {**q, "image_url": _public_materials_url(q["image_path"])}
    return q


def _normalize_question_fields(
    q_type: str, options: Optional[list[str]], correct_index: Optional[int]
) -> tuple[list[str], int]:
    """True/false always stores as a 2-option MCQ under the hood (§3/§9 —
    reusing the existing options/correct_index columns rather than a
    parallel schema per question type), so grading and rendering code
    never need to branch on type."""
    if q_type == "true_false":
        return ["Vrai", "Faux"], (correct_index if correct_index in (0, 1) else 0)
    if q_type != "multiple_choice":
        raise HTTPException(400, "Type de question invalide")
    opts = options or []
    if len(opts) < 2:
        raise HTTPException(400, "Une question à choix multiples doit avoir au moins 2 options.")
    idx = correct_index if correct_index is not None else 0
    if not (0 <= idx < len(opts)):
        raise HTTPException(400, "correct_index invalide pour cette question.")
    return opts, idx


def _validate_difficulty(value: str) -> None:
    if value not in ("easy", "medium", "hard"):
        raise HTTPException(400, "Difficulté invalide")


def _validate_points(value: float) -> None:
    if value is None or value <= 0:
        raise HTTPException(400, "Les points doivent être positifs")


# ────────────────────────────── exam CRUD ──────────────────────────────────

@router.get("")
async def list_exams(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if user.can_create():
        if user.is_admin():
            courses = db.from_("courses").select("id, title").execute().data or []
        else:
            courses = db.from_("courses").select("id, title").eq("professor_id", user.id).execute().data or []

        course_ids = [c["id"] for c in courses]
        course_map = {c["id"]: c["title"] for c in courses}
        if not course_ids:
            return []

        exams = (
            db.from_("exams").select("*").in_("course_id", course_ids).order("created_at", desc=True).execute().data or []
        )
        q_count: dict[str, int] = {}
        if exams:
            exam_ids = [e["id"] for e in exams]
            questions = db.from_("exam_questions").select("exam_id").in_("exam_id", exam_ids).execute().data or []
            for q in questions:
                q_count[q["exam_id"]] = q_count.get(q["exam_id"], 0) + 1

        return [
            {**e, "course_title": course_map.get(e["course_id"], "—"), "question_count": q_count.get(e["id"], 0)}
            for e in exams
        ]
    else:
        enrollments = (
            db.from_("course_enrollments").select("course_id").eq("student_id", user.id).execute().data or []
        )
        enrolled_ids = [e["course_id"] for e in enrollments]
        if not enrolled_ids:
            return []

        courses = db.from_("courses").select("id, title").in_("id", enrolled_ids).execute().data or []
        course_map = {c["id"]: c["title"] for c in courses}

        exams = (
            db.from_("exams")
            .select("*")
            .in_("course_id", enrolled_ids)
            .eq("is_published", True)
            .order("created_at", desc=True)
            .execute()
            .data or []
        )
        if not exams:
            return []

        exam_ids = [e["id"] for e in exams]
        questions = db.from_("exam_questions").select("exam_id").in_("exam_id", exam_ids).execute().data or []
        q_count: dict[str, int] = {}
        for q in questions:
            q_count[q["exam_id"]] = q_count.get(q["exam_id"], 0) + 1

        responses = (
            db.from_("exam_responses")
            .select("*")
            .eq("student_id", user.id)
            .in_("exam_id", exam_ids)
            .execute()
            .data or []
        )
        resp_map = {r["exam_id"]: r for r in responses}

        return [
            {
                **e,
                "course_title": course_map.get(e["course_id"], "—"),
                "question_count": q_count.get(e["id"], 0),
                "my_response": resp_map.get(e["id"]),
            }
            for e in exams
        ]


@router.post("")
async def create_exam(
    body: ExamCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Not authorized")
    course = _get_course_or_404(db, body.course_id)
    _require_course_owner(user, course)
    if body.type not in ("examen", "quiz"):
        raise HTTPException(400, "Type d'examen invalide")

    payload = {
        "title": body.title,
        "description": body.description,
        "duration_minutes": body.duration_minutes,
        "start_time": body.start_time,
        "course_id": body.course_id,
        "type": body.type,
        "is_published": False,
        "randomize_questions": body.randomize_questions,
        "randomize_answers": body.randomize_answers,
    }
    if body.content_scope is not None:
        payload["content_scope"] = body.content_scope.model_dump()
    if body.generation_config is not None:
        payload["generation_config"] = body.generation_config.model_dump()

    res = db.from_("exams").insert(payload).execute()
    exam = res.data[0]
    log_audit(db, user.id, "exam.create", "exam", exam["id"], {"course_id": body.course_id})

    for i, q in enumerate(body.questions):
        options, correct_index = _normalize_question_fields(q.type, q.options, q.correct_index)
        db.from_("exam_questions").insert({
            "exam_id": exam["id"], "question": q.question, "options": options,
            "correct_index": correct_index, "order_num": i,
            "type": q.type, "difficulty": q.difficulty, "points": q.points,
            "source_module_id": q.source_module_id, "source_lesson_id": q.source_lesson_id,
        }).execute()

    return exam


@router.get("/{exam_id}")
async def get_exam(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    exam = _get_exam_or_404(db, exam_id)
    course = _get_course_or_404(db, exam["course_id"])
    is_owner = user.is_admin() or course.get("professor_id") == user.id
    if not is_owner:
        if not exam.get("is_published"):
            raise HTTPException(403, "Cet examen n'est pas disponible")
        enrolled = (
            db.from_("course_enrollments").select("id")
            .eq("course_id", exam["course_id"]).eq("student_id", user.id).execute().data
        )
        if not enrolled:
            raise HTTPException(403, "Vous n'avez pas accès à cet examen")
    return {**exam, "course_title": course.get("title"), "is_editable": not _has_submissions(db, exam_id)}


@router.patch("/{exam_id}")
async def update_exam(
    exam_id: str,
    body: ExamUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _load_owned_exam(db, exam_id, user)
    _ensure_editable(db, exam_id)

    fields: dict = {}
    if body.title is not None:
        fields["title"] = body.title
    if body.description is not None:
        fields["description"] = body.description
    if body.duration_minutes is not None:
        if body.duration_minutes <= 0:
            raise HTTPException(400, "La durée doit être positive")
        fields["duration_minutes"] = body.duration_minutes
    if body.start_time is not None:
        fields["start_time"] = body.start_time
    if body.type is not None:
        if body.type not in ("examen", "quiz"):
            raise HTTPException(400, "Type d'examen invalide")
        fields["type"] = body.type
    if body.content_scope is not None:
        fields["content_scope"] = body.content_scope.model_dump()
    if body.generation_config is not None:
        fields["generation_config"] = body.generation_config.model_dump()
    if body.randomize_questions is not None:
        fields["randomize_questions"] = body.randomize_questions
    if body.randomize_answers is not None:
        fields["randomize_answers"] = body.randomize_answers

    if not fields:
        return _get_exam_or_404(db, exam_id)

    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = db.from_("exams").update(fields).eq("id", exam_id).execute()
    log_audit(db, user.id, "exam.update", "exam", exam_id, {"fields": list(fields.keys())})
    return res.data[0]


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _load_owned_exam(db, exam_id, user)
    if _has_submissions(db, exam_id):
        raise HTTPException(409, "Cet examen a des réponses d'étudiants — suppression impossible.")
    db.from_("exams").delete().eq("id", exam_id).execute()
    log_audit(db, user.id, "exam.delete", "exam", exam_id)
    return {"ok": True}


# ─────────────────────────────── questions ─────────────────────────────────

@router.get("/{exam_id}/questions")
async def get_questions(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    exam = _get_exam_or_404(db, exam_id)
    course = _get_course_or_404(db, exam["course_id"])
    is_owner = user.is_admin() or course.get("professor_id") == user.id

    if not is_owner:
        if not exam.get("is_published"):
            raise HTTPException(403, "Cet examen n'est pas disponible")
        enrolled = (
            db.from_("course_enrollments").select("id")
            .eq("course_id", exam["course_id"]).eq("student_id", user.id).execute().data
        )
        if not enrolled:
            raise HTTPException(403, "Vous n'avez pas accès à cet examen")

    questions = (
        db.from_("exam_questions").select("*").eq("exam_id", exam_id).order("order_num").execute().data or []
    )
    questions = [_with_image_url(q) for q in questions]
    if is_owner:
        return questions
    # Students: hide correct_index until they submit
    return [{k: v for k, v in q.items() if k != "correct_index"} for q in questions]


@router.post("/questions/generate")
async def generate_questions(
    body: GenerateQuestionsRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """AI-assisted QCM drafting, grounded in real IPAIS exam examples. Called
    while drafting an exam (before it's created), so it's keyed off course_id
    rather than exam_id. Returns drafts only — nothing is saved; the caller
    reviews/edits them client-side before the exam + questions are created.

    NOTE (Phase 1): still grounded only in the course title/topic, not the
    professor's actual selected module/lesson content — that's Phase 2's
    job (adapting this alongside generate_knowledge_questions()). Left
    untouched here beyond the ownership fix, per the explicit instruction
    not to build AI generation yet."""
    if not user.can_create():
        raise HTTPException(403, "Not authorized")
    course = _get_course_or_404(db, body.course_id)
    _require_course_owner(user, course)

    try:
        return generate_mcq_questions(course["title"], body.topic, body.num_questions)
    except ValueError as e:
        raise HTTPException(502, str(e))


@router.post("/{exam_id}/questions")
async def add_question(
    exam_id: str,
    body: QuestionCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _load_owned_exam(db, exam_id, user)
    _ensure_editable(db, exam_id)
    _validate_difficulty(body.difficulty)
    _validate_points(body.points)
    options, correct_index = _normalize_question_fields(body.type, body.options, body.correct_index)

    last = (
        db.from_("exam_questions").select("order_num")
        .eq("exam_id", exam_id).order("order_num", desc=True).limit(1).execute().data
    )
    next_order = (last[0]["order_num"] + 1) if last else 0

    res = db.from_("exam_questions").insert({
        "exam_id": exam_id,
        "question": body.question,
        "options": options,
        "correct_index": correct_index,
        "order_num": next_order,
        "type": body.type,
        "difficulty": body.difficulty,
        "points": body.points,
        "source_module_id": body.source_module_id,
        "source_lesson_id": body.source_lesson_id,
    }).execute()
    q = res.data[0]
    log_audit(db, user.id, "exam.question_add", "exam_question", q["id"], {"exam_id": exam_id})
    return q


@router.patch("/{exam_id}/questions/{question_id}")
async def update_question(
    exam_id: str,
    question_id: str,
    body: QuestionUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _load_owned_exam(db, exam_id, user)
    _ensure_editable(db, exam_id)

    rows = db.from_("exam_questions").select("*").eq("id", question_id).eq("exam_id", exam_id).execute().data
    if not rows:
        raise HTTPException(404, "Question introuvable")
    current = rows[0]

    new_type = body.type if body.type is not None else current["type"]
    new_options = body.options if body.options is not None else current["options"]
    new_correct = body.correct_index if body.correct_index is not None else current["correct_index"]
    options, correct_index = _normalize_question_fields(new_type, new_options, new_correct)

    fields: dict = {"type": new_type, "options": options, "correct_index": correct_index}
    if body.question is not None:
        fields["question"] = body.question
    if body.difficulty is not None:
        _validate_difficulty(body.difficulty)
        fields["difficulty"] = body.difficulty
    if body.points is not None:
        _validate_points(body.points)
        fields["points"] = body.points
    if body.source_module_id is not None:
        fields["source_module_id"] = body.source_module_id or None
    if body.source_lesson_id is not None:
        fields["source_lesson_id"] = body.source_lesson_id or None

    res = db.from_("exam_questions").update(fields).eq("id", question_id).execute()
    log_audit(db, user.id, "exam.question_update", "exam_question", question_id)
    return _with_image_url(res.data[0])


@router.delete("/{exam_id}/questions/{question_id}")
async def delete_question(
    exam_id: str,
    question_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _load_owned_exam(db, exam_id, user)
    _ensure_editable(db, exam_id)
    db.from_("exam_questions").delete().eq("id", question_id).eq("exam_id", exam_id).execute()
    log_audit(db, user.id, "exam.question_delete", "exam_question", question_id, {"exam_id": exam_id})
    return {"ok": True}


@router.put("/{exam_id}/questions/reorder")
async def reorder_questions(
    exam_id: str,
    body: QuestionsReorder,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Body carries the FULL set of this exam's question ids in their new
    display order — real question_id stays the identity, order_num is just
    a display detail (§9 principle, applied to the professor's own
    reordering here, not only student-facing randomization)."""
    _load_owned_exam(db, exam_id, user)
    _ensure_editable(db, exam_id)

    existing = db.from_("exam_questions").select("id").eq("exam_id", exam_id).execute().data or []
    existing_ids = {q["id"] for q in existing}
    if set(body.question_ids) != existing_ids or len(body.question_ids) != len(existing_ids):
        raise HTTPException(400, "La liste doit contenir exactement les questions de cet examen, sans doublon.")

    for i, qid in enumerate(body.question_ids):
        db.from_("exam_questions").update({"order_num": i}).eq("id", qid).eq("exam_id", exam_id).execute()
    log_audit(db, user.id, "exam.question_reorder", "exam", exam_id)
    return {"ok": True}


@router.post("/{exam_id}/questions/{question_id}/image")
async def upload_question_image(
    exam_id: str,
    question_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
):
    exam, _course = _load_owned_exam(db, exam_id, user)
    _ensure_editable(db, exam_id)

    rows = db.from_("exam_questions").select("id, image_path").eq("id", question_id).eq("exam_id", exam_id).execute().data
    if not rows:
        raise HTTPException(404, "Question introuvable")

    content_type = file.content_type or ""
    if content_type not in IMAGE_MIME_PREFIXES:
        raise HTTPException(400, "Format non supporté — utilisez JPEG, PNG ou WebP.")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(400, "Fichier vide")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "L'image dépasse la limite de 8 Mo")

    old_path = rows[0].get("image_path")
    safe_name = f"{int(time.time())}_{safe_filename(file.filename or 'image')}"
    storage_path = f"{exam['course_id']}/exam-images/{exam_id}/{question_id}/{safe_name}"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{MATERIALS_BUCKET}/{storage_path}",
            headers={
                "Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY,
                "Content-Type": content_type, "x-upsert": "false",
            },
            content=data,
        )
        if not resp.is_success:
            raise HTTPException(500, f"Échec du stockage de l'image ({resp.status_code}): {resp.text}")

    db.from_("exam_questions").update(
        {"image_path": storage_path, "image_caption": caption}
    ).eq("id", question_id).execute()

    if old_path:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.request(
                "DELETE",
                f"{SUPABASE_URL}/storage/v1/object/{MATERIALS_BUCKET}",
                headers={"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY, "Content-Type": "application/json"},
                json={"prefixes": [old_path]},
            )

    log_audit(db, user.id, "exam.question_image_upload", "exam_question", question_id)
    return {"image_path": storage_path, "image_url": _public_materials_url(storage_path), "image_caption": caption}


@router.delete("/{exam_id}/questions/{question_id}/image")
async def delete_question_image(
    exam_id: str,
    question_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _load_owned_exam(db, exam_id, user)
    _ensure_editable(db, exam_id)

    rows = db.from_("exam_questions").select("image_path").eq("id", question_id).eq("exam_id", exam_id).execute().data
    if not rows:
        raise HTTPException(404, "Question introuvable")
    path = rows[0].get("image_path")
    if path:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.request(
                "DELETE",
                f"{SUPABASE_URL}/storage/v1/object/{MATERIALS_BUCKET}",
                headers={"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY, "Content-Type": "application/json"},
                json={"prefixes": [path]},
            )
    db.from_("exam_questions").update({"image_path": None, "image_caption": None}).eq("id", question_id).execute()
    log_audit(db, user.id, "exam.question_image_delete", "exam_question", question_id)
    return {"ok": True}


# ──────────────────────────── publish / draft ───────────────────────────────

@router.put("/{exam_id}/publish")
async def toggle_publish(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    exam, course = _load_owned_exam(db, exam_id, user)
    new_val = not exam["is_published"]

    if new_val:
        qcount = len(db.from_("exam_questions").select("id").eq("exam_id", exam_id).execute().data or [])
        if qcount == 0:
            raise HTTPException(400, "Ajoutez au moins une question avant de publier.")

    db.from_("exams").update({"is_published": new_val}).eq("id", exam_id).execute()
    log_audit(db, user.id, "exam.publish" if new_val else "exam.unpublish", "exam", exam_id)

    # Notify enrolled students only when publishing (not when unpublishing)
    if new_val:
        try:
            exam_title = exam["title"]
            course_id = exam["course_id"]
            enrolled = (
                db.from_("course_enrollments")
                .select("student_id")
                .eq("course_id", course_id)
                .execute()
                .data or []
            )
            student_ids = [r["student_id"] for r in enrolled]
            notify_users(
                db,
                student_ids,
                f"Examen disponible : {exam_title}",
                "Un nouvel examen est maintenant disponible.",
                "success",
                f"/dashboard/exams?focus={exam_id}",
            )
            # Email enrolled students about the newly published exam
            try:
                if student_ids:
                    profiles = (
                        db.from_("profiles")
                        .select("email")
                        .in_("id", student_ids)
                        .execute()
                        .data or []
                    )
                    emails = [p["email"] for p in profiles if p.get("email")]
                    if emails:
                        send_email(
                            emails,
                            f"Examen disponible : {exam_title}",
                            (
                                f"<h2>Nouvel examen</h2>"
                                f"<p>L'examen <b>{exam_title}</b> est maintenant disponible.</p>"
                                f"<a href='https://ipisb.ma/dashboard/exams'>Passer l'examen</a>"
                            ),
                        )
            except Exception:
                pass
        except Exception:
            pass  # notification failure must never break the main operation

    return {"is_published": new_val}


# ───────────────────────────── student taking ──────────────────────────────

def _start_payload(exam: dict, row: dict) -> dict:
    deadline = None
    if row.get("started_at") and exam.get("duration_minutes"):
        deadline = (_parse_dt(row["started_at"]) + timedelta(minutes=exam["duration_minutes"])).isoformat()
    return {
        "started_at": row.get("started_at"),
        "deadline_at": deadline,
        "submitted": row.get("submitted_at") is not None,
    }


@router.post("/{exam_id}/start")
async def start_exam(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """§17/§22 — records an authoritative server-side start time the first
    time a student opens the exam, so the countdown survives a refresh and
    /submit can enforce the deadline instead of trusting the browser
    timer. Idempotent: re-opening an already-started (not yet submitted)
    exam returns the SAME started_at, it never resets the clock."""
    if user.can_create():
        raise HTTPException(403, "Seuls les étudiants passent des examens")
    exam = _get_exam_or_404(db, exam_id)
    if not exam.get("is_published"):
        raise HTTPException(403, "Cet examen n'est pas disponible")
    enrolled = (
        db.from_("course_enrollments").select("id")
        .eq("course_id", exam["course_id"]).eq("student_id", user.id).execute().data
    )
    if not enrolled:
        raise HTTPException(403, "Vous n'êtes pas inscrit à ce cours")

    existing = (
        db.from_("exam_responses").select("*")
        .eq("exam_id", exam_id).eq("student_id", user.id).execute().data
    )
    if existing:
        return _start_payload(exam, existing[0])

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        row = db.from_("exam_responses").insert({
            "exam_id": exam_id, "student_id": user.id,
            "started_at": now_iso, "submitted_at": None, "answers": {},
        }).execute().data[0]
    except Exception:
        # Lost a race with a concurrent /start call for the same student —
        # the unique (exam_id, student_id) constraint rejected our insert.
        existing = (
            db.from_("exam_responses").select("*")
            .eq("exam_id", exam_id).eq("student_id", user.id).execute().data
        )
        if not existing:
            raise
        row = existing[0]
    return _start_payload(exam, row)


@router.post("/{exam_id}/submit")
async def submit_exam(
    exam_id: str,
    body: ExamAnswers,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if user.can_create():
        raise HTTPException(403, "Only students can take exams")
    exam = _get_exam_or_404(db, exam_id)
    if not exam.get("is_published"):
        raise HTTPException(403, "Cet examen n'est pas disponible")

    existing_rows = (
        db.from_("exam_responses").select("*")
        .eq("exam_id", exam_id).eq("student_id", user.id).execute().data
    )
    existing = existing_rows[0] if existing_rows else None

    # §7/§20 — lock after first submission; no silent resubmission/rescoring.
    if existing and existing.get("submitted_at"):
        raise HTTPException(409, "Cet examen a déjà été soumis.")

    now = datetime.now(timezone.utc)
    started_at = _parse_dt(existing["started_at"]) if existing and existing.get("started_at") else now
    duration = exam.get("duration_minutes")
    if duration:
        deadline = started_at + timedelta(minutes=duration, seconds=SUBMIT_GRACE_SECONDS)
        if now > deadline:
            # §17 — authoritative: the frontend auto-submits the instant
            # its countdown hits zero, so anything landing well past the
            # deadline (+ network-latency grace) isn't a legitimate
            # "timer just expired" submission.
            raise HTTPException(403, "Le temps imparti pour cet examen est écoulé.")

    questions = (
        db.from_("exam_questions").select("id, correct_index, points")
        .eq("exam_id", exam_id).execute().data or []
    )
    score = sum(
        float(q.get("points") or 1)
        for q in questions
        if str(q["id"]) in body.answers and body.answers[str(q["id"])] == q["correct_index"]
    )
    total = sum(float(q.get("points") or 1) for q in questions)

    payload = {
        "exam_id": exam_id,
        "student_id": user.id,
        "answers": body.answers,
        "score": score,
        "total": total,
        "started_at": existing["started_at"] if existing and existing.get("started_at") else now.isoformat(),
        "submitted_at": now.isoformat(),
    }
    if existing:
        db.from_("exam_responses").update(payload).eq("id", existing["id"]).execute()
    else:
        db.from_("exam_responses").insert(payload).execute()
    return {"score": score, "total": total}


@router.get("/{exam_id}/result")
async def get_result(
    exam_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    resp = (
        db.from_("exam_responses")
        .select("*")
        .eq("exam_id", exam_id)
        .eq("student_id", user.id)
        .execute()
        .data
    )
    if not resp:
        raise HTTPException(404, "No response found")
    questions = (
        db.from_("exam_questions").select("*").eq("exam_id", exam_id).order("order_num").execute().data or []
    )
    return {"response": resp[0], "questions": [_with_image_url(q) for q in questions]}
