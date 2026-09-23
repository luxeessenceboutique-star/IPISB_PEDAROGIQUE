import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from supabase import Client

from deps import CurrentUser, get_current_user, get_db
from utils.audit import log_audit
from utils.dossier import analyze_dossier

router = APIRouter(prefix="/students", tags=["student-files"])

BUCKET = "student-files"
SIGNED_URL_TTL = 60 * 60  # 1 hour
# Profile photos feed document generation (student cards) long after upload,
# so their stored URL must not expire in practice.
PHOTO_URL_TTL = 60 * 60 * 24 * 365 * 10

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/jpeg": "jpg",
    "image/png": "png",
}

FILE_TYPES = {"cin", "bac", "photo", "cv", "motivation", "autre"}


def _check_student_access(db: Client, user: CurrentUser, student_id: str) -> dict:
    rows = db.from_("profiles").select("id, full_name, created_by").eq("id", student_id).execute().data
    if not rows:
        raise HTTPException(404, "Stagiaire introuvable")
    if not user.is_admin() and rows[0].get("created_by") != user.id:
        raise HTTPException(403, "Non autorisé pour ce stagiaire")
    return rows[0]


@router.get("/{student_id}/files")
async def list_student_files(
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    _check_student_access(db, user, student_id)
    return (
        db.from_("student_files")
        .select("*")
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .execute()
        .data or []
    )


@router.post("/{student_id}/files")
async def upload_student_file(
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    type: str = Form("autre"),
    file: UploadFile = File(...),
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    _check_student_access(db, user, student_id)

    if type not in FILE_TYPES:
        raise HTTPException(400, f"Type invalide. Utilisez : {', '.join(sorted(FILE_TYPES))}")
    content_type = file.content_type or ""
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if not ext:
        raise HTTPException(400, "Seuls les fichiers PDF, DOCX, JPG et PNG sont acceptés")
    if type == "photo" and ext not in ("jpg", "png"):
        raise HTTPException(400, "La photo doit être une image JPG ou PNG")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(400, "Fichier vide")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(400, "Le fichier dépasse la limite de 20 Mo")

    file_path = f"{student_id}/{secrets.token_hex(8)}.{ext}"
    try:
        db.storage.from_(BUCKET).upload(file_path, data, {"content-type": content_type})
    except Exception as e:
        raise HTTPException(500, f"Échec du stockage : {str(e)}")

    res = db.from_("student_files").insert({
        "student_id": student_id,
        "type": type,
        "filename": file.filename or f"fichier.{ext}",
        "file_path": file_path,
        "content_type": content_type,
        "uploaded_by": user.id,
    }).execute()
    new_file = res.data[0]

    # A dossier photo becomes the profile photo — it then shows on the student
    # header and gets stamped onto generated documents (student cards).
    if type == "photo":
        try:
            signed = db.storage.from_(BUCKET).create_signed_url(file_path, PHOTO_URL_TTL)
            photo_url = signed.get("signedURL") or signed.get("signed_url")
            if photo_url:
                db.from_("profiles").update({"photo_url": photo_url}).eq("id", student_id).execute()
        except Exception:
            pass  # photo linking is best-effort — the file itself is saved

    log_audit(db, user.id, "student_file.upload", "student_file", new_file["id"], {
        "student_id": student_id, "type": type, "filename": new_file["filename"],
    })
    return new_file


@router.get("/{student_id}/files/{file_id}/download")
async def download_student_file(
    student_id: str,
    file_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    _check_student_access(db, user, student_id)
    rows = db.from_("student_files").select("file_path").eq("id", file_id).eq("student_id", student_id).execute().data
    if not rows:
        raise HTTPException(404, "Fichier introuvable")
    signed = db.storage.from_(BUCKET).create_signed_url(rows[0]["file_path"], SIGNED_URL_TTL)
    return {"signed_url": signed.get("signedURL") or signed.get("signed_url")}


@router.delete("/{student_id}/files/{file_id}")
async def delete_student_file(
    student_id: str,
    file_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    _check_student_access(db, user, student_id)
    rows = db.from_("student_files").select("file_path, type").eq("id", file_id).eq("student_id", student_id).execute().data
    if not rows:
        raise HTTPException(404, "Fichier introuvable")
    try:
        db.storage.from_(BUCKET).remove([rows[0]["file_path"]])
    except Exception:
        pass  # storage cleanup is best-effort — don't block the row delete on it
    db.from_("student_files").delete().eq("id", file_id).execute()

    # If the deleted file was backing the profile photo, clear it so cards
    # fall back to the neutral placeholder instead of a dead URL.
    if rows[0]["type"] == "photo":
        try:
            profile = db.from_("profiles").select("photo_url").eq("id", student_id).execute().data
            if profile and rows[0]["file_path"] in (profile[0].get("photo_url") or ""):
                db.from_("profiles").update({"photo_url": None}).eq("id", student_id).execute()
        except Exception:
            pass

    log_audit(db, user.id, "student_file.delete", "student_file", file_id, {"student_id": student_id})
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────
# AI dossier analysis — the LLM reads every dossier file and extracts the
# student's info. Result is stored per student; GET serves the stored one
# (with a staleness flag when the file set changed), POST re-runs it.
# ─────────────────────────────────────────────────────────────────────────

def _analysis_payload(db: Client, student_id: str, row: dict) -> dict:
    current = db.from_("student_files").select("id").eq("student_id", student_id).execute().data or []
    current_ids = sorted(f["id"] for f in current)
    stored_ids = sorted(row.get("file_ids") or [])
    return {
        "analysis": row["data"],
        "analyzed_at": row["analyzed_at"],
        "file_count": len(stored_ids),
        "stale": current_ids != stored_ids,
    }


@router.get("/{student_id}/analysis")
async def get_student_analysis(
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    _check_student_access(db, user, student_id)
    rows = db.from_("student_analyses").select("*").eq("student_id", student_id).execute().data
    if not rows:
        return {"analysis": None}
    return _analysis_payload(db, student_id, rows[0])


@router.post("/{student_id}/analysis")
async def run_student_analysis(
    student_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Professor or admin only")
    _check_student_access(db, user, student_id)

    file_rows = (
        db.from_("student_files")
        .select("id, type, filename, file_path, content_type")
        .eq("student_id", student_id)
        .order("created_at")
        .execute()
        .data or []
    )
    # Identity photos carry no textual info — skip them rather than have the
    # vision model describe a portrait.
    doc_rows = [f for f in file_rows if f["type"] != "photo"]
    if not doc_rows:
        raise HTTPException(400, "Aucun document à analyser — ajoutez d'abord des fichiers au dossier (CIN, bac, CV…).")

    files = []
    for f in doc_rows:
        try:
            data = db.storage.from_(BUCKET).download(f["file_path"])
        except Exception:
            continue  # a missing storage object shouldn't sink the whole run
        files.append({"filename": f["filename"], "type": f["type"], "content_type": f["content_type"], "data": data})
    if not files:
        raise HTTPException(500, "Impossible de télécharger les fichiers du dossier.")

    profile = db.from_("profiles").select("full_name, email").eq("id", student_id).execute().data
    prof = profile[0] if profile else {}

    try:
        result = await run_in_threadpool(analyze_dossier, files, prof)
    except Exception as e:
        raise HTTPException(500, f"L'analyse IA a échoué : {str(e)}")

    row = {
        "student_id": student_id,
        "data": result,
        # Analyzed set = every dossier file (photos included): uploading or
        # deleting ANY file marks the analysis stale, which is what one expects.
        "file_ids": [f["id"] for f in file_rows],
        "analyzed_by": user.id,
        # DEFAULT now() only fires on insert — refresh explicitly on re-runs.
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
    res = db.from_("student_analyses").upsert(row).execute()
    saved = res.data[0]

    # The analysis fills the fiche administrative directly — no confirmation
    # step (same philosophy as templates: detect once, no admin re-approval).
    # Only extracted values are written; fields the documents didn't cover
    # keep whatever they held, and the Profil tab stays there for corrections.
    details = result.get("details") or {}
    applied = 0
    if details:
        try:
            db.from_("student_details").upsert({
                "student_id": student_id,
                **details,
                "updated_by": user.id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            applied = len(details)
        except Exception:
            pass  # a bad value must not sink the analysis itself

    log_audit(db, user.id, "student.analyze", "student", student_id, {
        "files": len(files), "infos": len(result.get("infos") or []), "applied": applied,
    })
    payload = _analysis_payload(db, student_id, saved)
    payload["applied"] = applied
    return payload
