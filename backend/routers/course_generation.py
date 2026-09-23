import os
import time
from datetime import datetime, timezone
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from supabase import Client

from deps import CurrentUser, get_current_user, get_db
from utils import docspace
from utils.audit import log_audit
from utils.course_generation import (
    edit_text_with_ai, gather_grounding_text, generate_lesson_content,
    generate_module_outline, regenerate_slide_with_ai,
)
from utils.course_pdf import render_course_pdf
from utils.course_pptx import build_deck_payload, render_course_pptx
from utils.course_slides import generate_slide_deck
from utils.safe_filename import safe_filename
from utils.slide_template_m101 import catalogue as slide_layout_catalogue

# Same prefix as courses.py/resources.py — distinct sub-paths, same convention
# already used to split one resource's endpoints across router files.
router = APIRouter(prefix="/courses", tags=["course-generation"])

# Same bucket resources.py writes course files to — the generated PDF shows
# up in the existing "Ressources" panel automatically, no new student-facing
# surface needed. A stable (non-timestamped) key means regenerating just
# overwrites the previous PDF instead of piling up duplicates.
MATERIALS_BUCKET = "course-materials"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _get_course_or_404(db: Client, course_id: str) -> dict:
    rows = db.from_("courses").select("*").eq("id", course_id).execute().data
    if not rows:
        raise HTTPException(404, "Cours introuvable")
    return rows[0]


def _require_owner(user: CurrentUser, course: dict) -> None:
    if not user.is_admin() and course.get("professor_id") != user.id:
        raise HTTPException(403, "Non autorisé")


def _resolve_specialty_id(db: Client, course_id: str) -> str | None:
    """A course's filière isn't stored directly — it's inferred from the
    class(es) it's assigned to. Falls back to None (général) if the course
    isn't assigned to any class yet, or is assigned to classes from more than
    one filière (ambiguous — safer to fall back than guess wrong)."""
    rows = (
        db.from_("class_courses").select("classes(specialty_id)")
        .eq("course_id", course_id).execute().data or []
    )
    specialty_ids = {
        r["classes"]["specialty_id"]
        for r in rows
        if r.get("classes") and r["classes"].get("specialty_id")
    }
    if len(specialty_ids) == 1:
        return specialty_ids.pop()
    return None


def _public_materials_url(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{MATERIALS_BUCKET}/{path}"


def _modules_with_lessons(db: Client, course_id: str, published_only: bool) -> list[dict]:
    query = db.from_("course_modules").select("*").eq("course_id", course_id)
    if published_only:
        query = query.eq("status", "published")
    modules = query.order("order_num").execute().data or []
    if not modules:
        return []
    module_ids = [m["id"] for m in modules]

    lesson_query = db.from_("course_lessons").select("*").in_("module_id", module_ids)
    if published_only:
        lesson_query = lesson_query.eq("status", "published")
    lessons = lesson_query.execute().data or []
    lesson_ids = [lesson["id"] for lesson in lessons]

    images_by_lesson: dict[str, list] = {}
    if lesson_ids:
        image_rows = (
            db.from_("course_lesson_images").select("*").in_("lesson_id", lesson_ids)
            .order("order_num").execute().data or []
        )
        for img in image_rows:
            images_by_lesson.setdefault(img["lesson_id"], []).append({
                "id": img["id"],
                "caption": img.get("caption"),
                "url": _public_materials_url(img["file_path"]),
                "file_path": img["file_path"],  # internal use (PDF embedding) — harmless to expose, it's just a storage path
            })

    by_module: dict[str, list] = {}
    for lesson in lessons:
        by_module.setdefault(lesson["module_id"], []).append({**lesson, "images": images_by_lesson.get(lesson["id"], [])})
    return [{**m, "lessons": by_module.get(m["id"], [])} for m in modules]


def _student_can_view(db: Client, user_id: str, course_id: str) -> bool:
    """Same enrollment signal courses.py's list_courses already uses for
    'which courses can this student see at all' (class membership → classes
    assigned to this course) — reusing it here rather than the separate
    course_enrollments table exams.py uses, so a student's course access is
    consistent everywhere in the app, not two different rules in two files."""
    student_classes = db.from_("class_students").select("class_id").eq("student_id", user_id).execute().data or []
    class_ids = [c["class_id"] for c in student_classes]
    if not class_ids:
        return False
    rows = (
        db.from_("class_courses").select("course_id")
        .eq("course_id", course_id).in_("class_id", class_ids).execute().data or []
    )
    return len(rows) > 0


@router.get("/{course_id}/modules")
async def list_modules(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = _get_course_or_404(db, course_id)
    is_owner = user.is_admin() or course.get("professor_id") == user.id
    if not is_owner and not _student_can_view(db, user.id, course_id):
        raise HTTPException(403, "Vous n'avez pas accès à ce cours")
    # students/other staff: published only — admin/owning prof see drafts too
    return _modules_with_lessons(db, course_id, published_only=not is_owner)


class ModuleCreate(BaseModel):
    title: Optional[str] = None
    objectives: Optional[str] = None
    hours_theory: Optional[float] = None
    hours_practice: Optional[float] = None


@router.post("/{course_id}/modules")
async def create_module(
    course_id: str,
    body: ModuleCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Manual chapter creation. "Générer le plan" (AI outline) is the normal
    path, but a prof adding one extra hand-written chapter — or extending a
    course past what the AI proposed — needs a plain add button too, the same
    way delete already exists per-chapter without needing regeneration."""
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    existing = (
        db.from_("course_modules").select("order_num").eq("course_id", course_id)
        .order("order_num", desc=True).limit(1).execute().data
    )
    next_order = (existing[0]["order_num"] + 1) if existing else 1

    res = db.from_("course_modules").insert({
        "course_id": course_id,
        "order_num": next_order,
        "title": (body.title or "").strip() or "Nouveau chapitre",
        "objectives": body.objectives or "",
        "hours_theory": body.hours_theory or 0,
        "hours_practice": body.hours_practice or 0,
        "status": "draft",
    }).execute()
    module = res.data[0]
    log_audit(db, user.id, "course.module_create", "course_module", module["id"])
    return module


@router.get("/{course_id}/progress")
async def get_progress(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Powers both the 'X/Y chapitres terminés' indicator and 'resume where
    I left off' — last_module_id is just the most recently visited chapter."""
    course = _get_course_or_404(db, course_id)
    is_owner = user.is_admin() or course.get("professor_id") == user.id
    if not is_owner and not _student_can_view(db, user.id, course_id):
        raise HTTPException(403, "Vous n'avez pas accès à ce cours")

    rows = (
        db.from_("course_progress").select("module_id, completed_at")
        .eq("student_id", user.id).eq("course_id", course_id)
        .order("completed_at", desc=True).execute().data or []
    )
    total = len(_modules_with_lessons(db, course_id, published_only=not is_owner))
    completed_ids = [r["module_id"] for r in rows]
    return {
        "completed_module_ids": completed_ids,
        "last_module_id": rows[0]["module_id"] if rows else None,
        "total_chapters": total,
        "percent": round(len(completed_ids) / total * 100) if total else 0,
    }


@router.post("/{course_id}/modules/{module_id}/progress")
async def mark_progress(
    course_id: str,
    module_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Called by the reader every time a student opens a chapter. Professors
    previewing their own course ('Aperçu élève') don't get progress rows —
    that's not a real student's progress, it'd just be noise."""
    course = _get_course_or_404(db, course_id)
    is_owner = user.is_admin() or course.get("professor_id") == user.id
    if is_owner:
        return {"tracked": False}
    if not _student_can_view(db, user.id, course_id):
        raise HTTPException(403, "Vous n'avez pas accès à ce cours")

    db.from_("course_progress").upsert(
        {"student_id": user.id, "course_id": course_id, "module_id": module_id, "completed_at": "now()"},
        on_conflict="student_id,module_id",
    ).execute()
    return {"tracked": True}


@router.post("/{course_id}/generate-pdf")
async def generate_pdf(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Compiles all PUBLISHED chapters into one PDF and drops it into the
    course's existing Resources (course-materials bucket) — students see it
    exactly where they already look for course files, no new page needed."""
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    modules = _modules_with_lessons(db, course_id, published_only=True)
    if not modules:
        raise HTTPException(400, "Aucun chapitre publié — publiez au moins un chapitre avant de générer le PDF.")

    # render_course_pdf does no I/O of its own — download each lesson's
    # images here and hand it raw bytes.
    for m in modules:
        for lesson in m.get("lessons") or []:
            for img in lesson.get("images") or []:
                try:
                    img["data"] = db.storage.from_(MATERIALS_BUCKET).download(img["file_path"])
                except Exception:
                    img["data"] = None  # skip a broken image rather than fail the whole PDF

    pdf_bytes = render_course_pdf(course, modules)

    clean_title = safe_filename(course.get("title") or "cours")
    # Stable key (no timestamp) so regenerating overwrites in place instead of
    # accumulating a new file in Resources every time.
    storage_path = f"{course_id}/files/genpdf_Cours_complet_-_{clean_title}.pdf"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{MATERIALS_BUCKET}/{storage_path}",
            headers={
                "Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY,
                "Content-Type": "application/pdf", "x-upsert": "true",
            },
            content=pdf_bytes,
        )
        if not resp.is_success:
            raise HTTPException(500, f"Échec du stockage du PDF ({resp.status_code}): {resp.text}")

    generated_at = datetime.now(timezone.utc).isoformat()
    # So the UI can warn "this PDF is behind what's published" the next time
    # a chapter gets published without anyone having to compare page counts.
    db.from_("courses").update({
        "pdf_generated_at": generated_at, "pdf_chapter_count": len(modules),
    }).eq("id", course_id).execute()

    log_audit(db, user.id, "course.generate_pdf", "course", course_id, {"chapters": len(modules), "size_bytes": len(pdf_bytes)})
    return {
        "title": f"Cours complet - {course.get('title')}.pdf",
        "url": f"{SUPABASE_URL}/storage/v1/object/public/{MATERIALS_BUCKET}/{storage_path}",
        "size_bytes": len(pdf_bytes),
        "chapters": len(modules),
        "generated_at": generated_at,
    }


def _build_pptx_bytes(db: Client, course: dict, modules: list[dict]) -> bytes:
    # One representative image per chapter (first uploaded, if any) — the
    # deck's own template still draws a labelled empty frame for the
    # professor to fill in PowerPoint when a chapter has none.
    chapter_images: dict[str, bytes | None] = {}
    for m in modules:
        images = ((m.get("lessons") or [{}])[0] or {}).get("images") or []
        data = None
        if images:
            try:
                data = db.storage.from_(MATERIALS_BUCKET).download(images[0]["file_path"])
            except Exception:
                data = None
        chapter_images[m["id"]] = data

    payload = build_deck_payload(course, modules, chapter_images)
    try:
        return render_course_pptx(payload)
    except RuntimeError as e:
        raise HTTPException(500, f"Échec de la génération du support PowerPoint : {e}")


@router.post("/{course_id}/generate-pptx")
async def generate_pptx(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Fills the client-approved IPISB PowerPoint template (pptx_export/,
    design lifted verbatim, not reimplemented) with the course's PUBLISHED
    chapters and drops a static copy into Resources next to the PDF — for
    the *live, in-platform* editable version see /docspace-editor below."""
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    modules = _modules_with_lessons(db, course_id, published_only=True)
    if not modules:
        raise HTTPException(400, "Aucun chapitre publié — publiez au moins un chapitre avant de générer le support.")

    pptx_bytes = _build_pptx_bytes(db, course, modules)

    clean_title = safe_filename(course.get("title") or "cours")
    storage_path = f"{course_id}/files/genpptx_Support_PowerPoint_-_{clean_title}.pptx"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{MATERIALS_BUCKET}/{storage_path}",
            headers={
                "Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY,
                "Content-Type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "x-upsert": "true",
            },
            content=pptx_bytes,
        )
        if not resp.is_success:
            raise HTTPException(500, f"Échec du stockage du support ({resp.status_code}): {resp.text}")

    log_audit(db, user.id, "course.generate_pptx", "course", course_id, {"chapters": len(modules), "size_bytes": len(pptx_bytes)})
    return {
        "title": f"Support PowerPoint - {course.get('title')}.pptx",
        "url": f"{SUPABASE_URL}/storage/v1/object/public/{MATERIALS_BUCKET}/{storage_path}",
        "size_bytes": len(pptx_bytes),
        "chapters": len(modules),
    }


@router.post("/{course_id}/docspace-editor")
async def open_docspace_editor(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Opens a LIVE, in-platform editable deck (ONLYOFFICE DocSpace), as
    opposed to /generate-pptx's static download. First call generates the
    deck and uploads it to DocSpace; every call after that reopens the SAME
    DocSpace file — regenerating from scratch on every click would silently
    overwrite whatever the professor already changed there. Regenerating on
    purpose (e.g. after publishing new chapters) isn't wired yet — v1 is
    "start once, keep editing the same live copy"."""
    if not docspace.configured():
        raise HTTPException(503, "L'éditeur en direct n'est pas configuré sur ce serveur (DOCSPACE_* manquant).")

    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    existing_id = course.get("docspace_file_id")
    if existing_id:
        return {"fileId": existing_id, "docspaceUrl": docspace.DOCSPACE_URL, "created": False}

    modules = _modules_with_lessons(db, course_id, published_only=True)
    if not modules:
        raise HTTPException(400, "Aucun chapitre publié — publiez au moins un chapitre avant d'ouvrir l'éditeur.")

    pptx_bytes = _build_pptx_bytes(db, course, modules)
    clean_title = safe_filename(course.get("title") or "cours")

    try:
        uploaded = await docspace.upload_deck(f"{clean_title}.pptx", pptx_bytes)
    except Exception as e:
        raise HTTPException(502, f"Échec de l'envoi vers l'éditeur en direct : {e}")

    db.from_("courses").update({"docspace_file_id": uploaded["id"]}).eq("id", course_id).execute()
    log_audit(db, user.id, "course.docspace_editor_open", "course", course_id, {"docspace_file_id": uploaded["id"]})
    return {"fileId": uploaded["id"], "docspaceUrl": docspace.DOCSPACE_URL, "created": True}


@router.post("/{course_id}/generate/outline")
async def generate_outline(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    specialty_id = _resolve_specialty_id(db, course_id)
    # Course title + description prioritize which reference documents (and
    # which passages within them) actually get used, instead of "whatever's
    # tagged to this filière, in upload order" — see gather_grounding_text.
    relevance_hint = " ".join(filter(None, [course.get("title"), course.get("description")]))
    grounding = gather_grounding_text(
        db, specialty_id, ["cdc", "programmes", "fiches_examens"], relevance_hint=relevance_hint,
    )
    if not grounding:
        raise HTTPException(
            400,
            "Aucun document de référence trouvé pour la filière de ce cours. "
            "Ajoutez des documents dans la Bibliothèque de référence d'abord.",
        )

    # Already-published chapters are never touched by this endpoint, but the
    # model needs to know they exist — otherwise it plans the whole UF from
    # scratch again and hands back a duplicate "Introduction" chapter with no
    # idea one is already live. Numbering also has to continue after them:
    # restarting at 1 collided with the published chapters' own order_num.
    published = (
        db.from_("course_modules").select("title, order_num").eq("course_id", course_id)
        .eq("status", "published").order("order_num").execute().data or []
    )
    next_order = (max((p["order_num"] for p in published), default=0)) + 1

    try:
        modules = generate_module_outline(
            course["title"], course.get("semester") or "—", grounding,
            already_published=[p["title"] for p in published] or None,
            description=course.get("description"),
        )
    except ValueError as e:
        raise HTTPException(502, str(e))

    # A fresh outline replaces any previous UNPUBLISHED attempt — published
    # chapters are left alone so regenerating never silently deletes work
    # that's already live for students.
    db.from_("course_modules").delete().eq("course_id", course_id).eq("status", "draft").execute()

    saved = []
    for offset, m in enumerate(modules):
        res = db.from_("course_modules").insert({
            "course_id": course_id,
            "order_num": next_order + offset,
            "title": m["title"],
            "objectives": m["objectives"],
            "hours_theory": m["hours_theory"],
            "hours_practice": m["hours_practice"],
            "status": "draft",
            "source_specialty_id": specialty_id,
            "generated_at": "now()",
        }).execute()
        saved.append(res.data[0])

    log_audit(db, user.id, "course.generate_outline", "course", course_id, {"chapters": len(saved), "continued_after": next_order - 1})
    return saved


@router.post("/{course_id}/modules/{module_id}/generate-lesson")
async def generate_lesson(
    course_id: str,
    module_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    modules = db.from_("course_modules").select("*").eq("id", module_id).eq("course_id", course_id).execute().data
    if not modules:
        raise HTTPException(404, "Chapitre introuvable")
    module = modules[0]

    specialty_id = module.get("source_specialty_id") or _resolve_specialty_id(db, course_id)
    # Chapter title + objectives are a sharper relevance signal than the
    # course-level one — same reasoning as generate_outline above.
    relevance_hint = " ".join(filter(None, [module.get("title"), module.get("objectives"), course.get("description")]))
    # Wider net + bigger budget than the outline stage — depth here needs more
    # source material than a chapter list does.
    grounding = gather_grounding_text(
        db, specialty_id, ["cdc", "programmes", "fiches_examens"], char_budget=20000, relevance_hint=relevance_hint,
    )

    try:
        content = generate_lesson_content(course["title"], module["title"], module.get("objectives") or "", grounding)
    except ValueError as e:
        raise HTTPException(502, str(e))

    existing = db.from_("course_lessons").select("id").eq("module_id", module_id).execute().data
    if existing:
        res = db.from_("course_lessons").update({
            "content": content, "status": "draft", "generated_at": "now()", "updated_at": "now()",
        }).eq("id", existing[0]["id"]).execute()
    else:
        res = db.from_("course_lessons").insert({
            "module_id": module_id, "order_num": 1, "title": module["title"],
            "content": content, "status": "draft", "generated_at": "now()", "updated_at": "now()",
        }).execute()

    log_audit(db, user.id, "course.generate_lesson", "course_module", module_id)
    return res.data[0]


@router.get("/slide-layouts")
async def list_slide_layouts(
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """The M101 layout catalogue for the editor's « Ajouter une diapositive »
    picker.

    Served rather than duplicated in TypeScript so the gabarits a teacher
    inserts by hand are byte-for-byte the ones generation produces — the
    alternative was maintaining ~15 layouts' worth of coordinates in two
    languages and watching them drift. Every layout comes back as plain
    elements, so an inserted gabarit is as editable as anything else on the
    canvas.

    Safe to sit on a single path segment: no `GET /courses/{course_id}`
    exists in any router, so this can't be swallowed by a wildcard.
    """
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    return slide_layout_catalogue()


@router.post("/{course_id}/modules/{module_id}/generate-slides")
async def generate_slides(
    course_id: str,
    module_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    force: bool = False,
):
    """Seeds the visual editor's deck from the chapter's already-generated
    text (see utils/course_slides.py) — this is what turns a blank canvas
    into a starting point once a teacher opens the editor for a chapter
    that already has AI content. Never overwrites a deck that already has
    slides unless force=true, so a teacher's own hand-built work can't be
    silently clobbered by clicking this again."""
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    modules = db.from_("course_modules").select("*").eq("id", module_id).eq("course_id", course_id).execute().data
    if not modules:
        raise HTTPException(404, "Chapitre introuvable")
    module = modules[0]

    lessons = db.from_("course_lessons").select("*").eq("module_id", module_id).order("order_num").execute().data
    if not lessons:
        raise HTTPException(400, "Générez d'abord le contenu du chapitre avant de créer les diapositives.")
    lesson = lessons[0]
    if not (lesson.get("content") or "").strip():
        raise HTTPException(400, "Générez d'abord le contenu du chapitre avant de créer les diapositives.")
    if lesson.get("slides") and not force:
        raise HTTPException(409, "Ce chapitre a déjà des diapositives — relancez avec force=true pour les remplacer.")

    images = (
        db.from_("course_lesson_images").select("file_path").eq("lesson_id", lesson["id"])
        .order("order_num").execute().data or []
    )
    image_urls = [_public_materials_url(img["file_path"]) for img in images]

    slides = generate_slide_deck(
        module["title"], module.get("objectives"), lesson["content"], image_urls,
        # The chapter's position and volume horaire drive the template's own
        # chrome (the "CHAPITRE n" tab, the kicker line, the hours badge), so
        # they have to travel with the content rather than be re-typed.
        chapter_number=module.get("order_num") or 1,
        hours=(module.get("hours_theory") or 0) + (module.get("hours_practice") or 0),
    )

    db.from_("course_lessons").update({"slides": slides, "updated_at": "now()"}).eq("id", lesson["id"]).execute()
    log_audit(db, user.id, "course.generate_slides", "course_module", module_id)
    return {"slides": slides}


class AIEditTextBody(BaseModel):
    text: str
    instruction: str


@router.post("/{course_id}/ai-edit-text")
async def ai_edit_text(
    course_id: str,
    body: AIEditTextBody,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Phase 7 (spec §17) — select a text element in the slide editor, ask
    AI to modify it ('simplify this', 'add a Morocco example', ...).
    Deliberately stateless: this only rewrites text and hands it back —
    the editor applies the result to its own local state (through the same
    undo-tracked commit() as any manual edit) and the teacher saves
    normally. Nothing is persisted here, so a bad AI result costs nothing
    but an Undo."""
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)
    if not body.instruction.strip():
        raise HTTPException(400, "Instruction manquante")
    try:
        new_text = edit_text_with_ai(body.text, body.instruction)
    except ValueError as e:
        raise HTTPException(502, str(e))
    log_audit(db, user.id, "course.ai_edit_text", "course", course_id)
    return {"text": new_text}


class AIRegenerateSlideBody(BaseModel):
    texts: list[str]
    instruction: str


@router.post("/{course_id}/ai-regenerate-slide")
async def ai_regenerate_slide(
    course_id: str,
    body: AIRegenerateSlideBody,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Whole-slide AI editing — extends ai_edit_text from 'rewrite this one
    text box' to 'restructure everything on this slide' (add/remove/reshape
    text blocks, not just reword what's already there). Stateless like
    ai_edit_text: returns role+content pairs, the editor lays them out and
    the teacher saves normally — images/shapes on the slide are never sent
    here and never touched by this endpoint."""
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)
    if not body.instruction.strip():
        raise HTTPException(400, "Instruction manquante")
    try:
        items = regenerate_slide_with_ai(body.texts, body.instruction)
    except ValueError as e:
        raise HTTPException(502, str(e))
    log_audit(db, user.id, "course.ai_regenerate_slide", "course", course_id)
    return {"items": items}


class ModuleUpdate(BaseModel):
    title: Optional[str] = None
    objectives: Optional[str] = None
    hours_theory: Optional[float] = None
    hours_practice: Optional[float] = None
    status: Optional[str] = None  # "draft" | "published"


@router.patch("/{course_id}/modules/{module_id}")
async def update_module(
    course_id: str,
    module_id: str,
    body: ModuleUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in ("draft", "published"):
        raise HTTPException(400, "status invalide")
    if fields:
        db.from_("course_modules").update(fields).eq("id", module_id).eq("course_id", course_id).execute()

    rows = db.from_("course_modules").select("*").eq("id", module_id).execute().data
    if not rows:
        raise HTTPException(404, "Chapitre introuvable")
    if fields.get("status"):
        log_audit(db, user.id, f"course.module_{fields['status']}", "course_module", module_id)
    return rows[0]


@router.delete("/{course_id}/modules/{module_id}")
async def delete_module(
    course_id: str,
    module_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)
    db.from_("course_modules").delete().eq("id", module_id).eq("course_id", course_id).execute()
    log_audit(db, user.id, "course.module_delete", "course_module", module_id)
    return {"ok": True}


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None  # "draft" | "published"
    slides: Optional[list] = None  # Phase 2 visual editor's slide deck (list of slide objects)


@router.patch("/{course_id}/modules/{module_id}/lessons/{lesson_id}")
async def update_lesson(
    course_id: str,
    module_id: str,
    lesson_id: str,
    body: LessonUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    fields = body.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in ("draft", "published"):
        raise HTTPException(400, "status invalide")
    if fields:
        # Any edit here (content, title, or status) can make the last-compiled
        # PDF stale — stamp it so the panel's staleness check can catch a
        # content edit to an already-published chapter, not just a
        # publish/unpublish that changes the chapter count.
        db.from_("course_lessons").update({**fields, "updated_at": "now()"}).eq("id", lesson_id).eq("module_id", module_id).execute()

    rows = db.from_("course_lessons").select("*").eq("id", lesson_id).execute().data
    if not rows:
        raise HTTPException(404, "Leçon introuvable")
    if fields.get("status"):
        log_audit(db, user.id, f"course.lesson_{fields['status']}", "course_lesson", lesson_id)
    return rows[0]


IMAGE_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp")


@router.post("/{course_id}/modules/{module_id}/lessons/{lesson_id}/images")
async def upload_lesson_image(
    course_id: str,
    module_id: str,
    lesson_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
):
    """Lets the professor illustrate a chapter with their own image (a real
    diagram they already have, a clinical photo, a schema) — embedded into
    the compiled PDF right after the chapter's text."""
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    lessons = db.from_("course_lessons").select("id").eq("id", lesson_id).eq("module_id", module_id).execute().data
    if not lessons:
        raise HTTPException(404, "Leçon introuvable")

    content_type = file.content_type or ""
    if content_type not in IMAGE_MIME_PREFIXES:
        raise HTTPException(400, "Format non supporté — utilisez JPEG, PNG ou WebP.")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(400, "Fichier vide")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(400, "L'image dépasse la limite de 8 Mo")

    safe_name = f"{int(time.time())}_{safe_filename(file.filename or 'image')}"
    storage_path = f"{course_id}/lesson-images/{lesson_id}/{safe_name}"

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

    existing_count = len(db.from_("course_lesson_images").select("id").eq("lesson_id", lesson_id).execute().data or [])
    res = db.from_("course_lesson_images").insert({
        "lesson_id": lesson_id,
        "file_path": storage_path,
        "caption": caption,
        "order_num": existing_count + 1,
        "uploaded_by": user.id,
    }).execute()
    row = res.data[0]

    log_audit(db, user.id, "course.lesson_image_upload", "course_lesson", lesson_id)
    return {
        "id": row["id"], "caption": row.get("caption"),
        "url": _public_materials_url(storage_path), "file_path": storage_path,
    }


@router.delete("/{course_id}/modules/{module_id}/lessons/{lesson_id}/images/{image_id}")
async def delete_lesson_image(
    course_id: str,
    module_id: str,
    lesson_id: str,
    image_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = _get_course_or_404(db, course_id)
    _require_owner(user, course)

    rows = db.from_("course_lesson_images").select("*").eq("id", image_id).eq("lesson_id", lesson_id).execute().data
    if not rows:
        raise HTTPException(404, "Image introuvable")
    file_path = rows[0]["file_path"]

    async with httpx.AsyncClient(timeout=30) as client:
        await client.request(
            "DELETE",
            f"{SUPABASE_URL}/storage/v1/object/{MATERIALS_BUCKET}",
            headers={"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY, "Content-Type": "application/json"},
            json={"prefixes": [file_path]},
        )
    db.from_("course_lesson_images").delete().eq("id", image_id).execute()
    log_audit(db, user.id, "course.lesson_image_delete", "course_lesson", lesson_id)
    return {"ok": True}
