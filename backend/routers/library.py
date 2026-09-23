import logging
import os
import time
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from supabase import Client

from deps import CurrentUser, get_current_user, get_db
from utils.audit import log_audit
from utils.safe_filename import safe_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library", tags=["library"])

BUCKET = "reference-library"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Fixed categories so the UI can show stable tabs.
CATEGORIES = ["cdc", "programmes", "fiches_examens", "reglements", "autres"]

# Filière-specific categories: a specialty_id is required on upload and
# usable as a filter on list. reglements/autres stay institution-wide.
SPECIALTY_SCOPED = {"cdc", "programmes", "fiches_examens"}


def _storage_headers(content_type: str = "application/octet-stream") -> dict:
    return {"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY, "Content-Type": content_type}


def _public_url(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"


def _require_staff(user: CurrentUser):
    if not (user.is_admin() or user.is_prof()):
        raise HTTPException(403, "Staff only")


def _my_specialty_ids(db: Client, user_id: str) -> set[str]:
    """A professor's filière(s) — inferred from the classes they created,
    since there's no direct professor->specialty table. Admins bypass this
    entirely (see call sites); this is only ever consulted for professors."""
    rows = (
        db.from_("classes").select("specialty_id").eq("created_by", user_id).execute().data or []
    )
    return {r["specialty_id"] for r in rows if r.get("specialty_id")}


@router.get("/categories")
async def list_categories(user: Annotated[CurrentUser, Depends(get_current_user)]):
    _require_staff(user)
    return CATEGORIES


@router.get("/{category}")
async def list_files(
    category: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    specialty_id: Optional[str] = None,
):
    _require_staff(user)
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown category")

    query = db.from_("library_files").select("*, specialties(name)").eq("category", category)

    # Admins see every filière's documents, always. A professor only sees
    # their own filière(s) — inferred from the classes they created — plus
    # anything genuinely institution-wide (specialty_id IS NULL, e.g. a
    # single "Liste des Coefficients" that covers several filières at once).
    if not user.is_admin() and category in SPECIALTY_SCOPED:
        my_specialties = _my_specialty_ids(db, user.id)
        if specialty_id:
            if specialty_id not in my_specialties:
                raise HTTPException(403, "Ce n'est pas votre filière")
            query = query.eq("specialty_id", specialty_id)
        elif my_specialties:
            query = query.or_(f"specialty_id.in.({','.join(my_specialties)}),specialty_id.is.null")
        else:
            query = query.is_("specialty_id", "null")
    elif specialty_id:
        query = query.eq("specialty_id", specialty_id)

    rows = query.order("created_at", desc=True).execute().data or []

    return [
        {
            "id": r["id"],
            "title": r["title"],
            "url": _public_url(r["file_path"]),
            "size_bytes": r.get("size_bytes"),
            "mime_type": r.get("mime_type"),
            "created_at": r.get("created_at"),
            "specialty_id": r.get("specialty_id"),
            "specialty_name": (r.get("specialties") or {}).get("name"),
            "uploaded_by": r.get("uploaded_by"),
            # Admin can always delete; a prof can delete what they uploaded.
            "can_delete": user.is_admin() or r.get("uploaded_by") == user.id,
        }
        for r in rows
    ]


@router.post("/{category}/upload")
async def upload_file(
    category: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    file: UploadFile = File(...),
    specialty_id: Optional[str] = Form(None),
):
    _require_staff(user)
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown category")
    if category not in SPECIALTY_SCOPED:
        specialty_id = None  # reglements/autres are institution-wide, ignore any value sent
    # else: specialty_id stays optional even for scoped categories — NULL means
    # "toutes filières / général" (some real documents, e.g. a single "Liste des
    # Coefficients" file covering 3 filières at once, genuinely aren't one filière).
    elif specialty_id and not user.is_admin():
        if specialty_id not in _my_specialty_ids(db, user.id):
            raise HTTPException(403, "Ce n'est pas votre filière")

    content_type = file.content_type or "application/octet-stream"
    clean = safe_filename(file.filename or "file")
    safe_name = f"{int(time.time())}_{clean}"
    path = f"{category}/{safe_name}"
    content = await file.read()

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}",
            headers={**_storage_headers(content_type), "x-upsert": "false"},
            content=content,
        )
        if not resp.is_success:
            raise HTTPException(500, f"Storage upload failed ({resp.status_code}): {resp.text}")

    res = db.from_("library_files").insert({
        "category": category,
        "specialty_id": specialty_id,
        "file_path": path,
        "title": file.filename or safe_name,
        "mime_type": content_type,
        "size_bytes": len(content),
        "uploaded_by": user.id,
    }).execute()
    row = res.data[0]

    log_audit(db, user.id, "library.upload", "library_file", row["id"], {
        "category": category, "title": row["title"], "specialty_id": specialty_id,
    })
    return {
        "id": row["id"],
        "title": row["title"],
        "url": _public_url(path),
        "size_bytes": row["size_bytes"],
        "mime_type": content_type,
        "specialty_id": specialty_id,
        "specialty_name": None,
        "uploaded_by": user.id,
        "can_delete": True,
    }


@router.delete("/{category}/{file_id}")
async def delete_file(
    category: str,
    file_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    _require_staff(user)
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown category")

    rows = db.from_("library_files").select("*").eq("id", file_id).execute().data
    if not rows:
        raise HTTPException(404, "File not found")
    row = rows[0]
    if not (user.is_admin() or row.get("uploaded_by") == user.id):
        raise HTTPException(403, "You can only delete files you uploaded")

    async with httpx.AsyncClient(timeout=30) as client:
        await client.request(
            "DELETE",
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}",
            headers=_storage_headers("application/json"),
            json={"prefixes": [row["file_path"]]},
        )
    db.from_("library_files").delete().eq("id", file_id).execute()
    log_audit(db, user.id, "library.delete", "library_file", file_id, {"category": category})
    return {"ok": True}
