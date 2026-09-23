import json
import logging
import os
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Annotated
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from utils.safe_filename import safe_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/courses", tags=["resources"])

BUCKET = "course-materials"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _storage_headers(content_type: str = "application/octet-stream") -> dict:
    return {
        "Authorization": f"Bearer {SERVICE_KEY}",
        "apikey": SERVICE_KEY,
        "Content-Type": content_type,
    }

def _can_manage(user: CurrentUser, course_rows: list) -> bool:
    if not course_rows:
        return False
    return user.is_admin() or course_rows[0]["professor_id"] == user.id

def _public_url(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"


# ── List resources ────────────────────────────────────────────
@router.get("/{course_id}/resources")
async def list_resources(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    resources = []

    async with httpx.AsyncClient(timeout=30) as client:
        # List files
        list_resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/list/{BUCKET}",
            headers=_storage_headers("application/json"),
            json={"prefix": f"{course_id}/files", "limit": 200, "sortBy": {"column": "created_at", "order": "desc"}},
        )
        if list_resp.status_code == 200:
            for f in list_resp.json():
                name = f.get("name", "")
                if not name:
                    continue
                path = f"{course_id}/files/{name}"
                # Strip timestamp prefix from display name
                display = name.split("_", 1)[1] if "_" in name else name
                meta = f.get("metadata") or {}
                resources.append({
                    "id": f"file-{name}",
                    "type": "file",
                    "title": display,
                    "url": _public_url(path),
                    "size_bytes": meta.get("size"),
                    "mime_type": meta.get("mimetype"),
                })

        # Load links + videos from _meta.json
        meta_resp = await client.get(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{course_id}/_meta.json",
            headers={"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY},
        )
        if meta_resp.status_code == 200:
            try:
                meta = meta_resp.json()
                resources.extend(meta.get("items", []))
            except Exception:
                pass

    return resources


# ── Upload file ───────────────────────────────────────────────
@router.post("/{course_id}/resources/upload")
async def upload_file(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    file: UploadFile = File(...),
):
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    logger.info(f"UPLOAD: user={user.id} roles={user.roles} course_id={course_id} course={course}")
    if not _can_manage(user, course):
        logger.warning(f"UPLOAD DENIED: user={user.id} is_admin={user.is_admin()} course={course}")
        raise HTTPException(403, "Not authorized")

    content_type = file.content_type or "application/octet-stream"
    # Sanitize filename: replace any character that isn't alphanumeric, dot, hyphen, or underscore
    clean = safe_filename(file.filename or "file")
    safe_name = f"{int(time.time())}_{clean}"
    path = f"{course_id}/files/{safe_name}"
    content = await file.read()

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}",
            headers={
                "Authorization": f"Bearer {SERVICE_KEY}",
                "apikey": SERVICE_KEY,
                "Content-Type": content_type,
                "x-upsert": "false",
            },
            content=content,
        )
        if not resp.is_success:
            raise HTTPException(500, f"Storage upload failed ({resp.status_code}): {resp.text}")

    return {
        "id": f"file-{safe_name}",
        "type": "file",
        "title": file.filename,
        "url": _public_url(path),
        "size_bytes": len(content),
        "mime_type": content_type,
    }


# ── Save link / video metadata ────────────────────────────────
class MetaItem(BaseModel):
    id: str
    type: str
    title: str
    url: str


@router.post("/{course_id}/resources/meta")
async def save_meta(
    course_id: str,
    items: list[MetaItem],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    logger.info(f"META: user={user.id} roles={user.roles} course_id={course_id} course={course}")
    if not _can_manage(user, course):
        logger.warning(f"META DENIED: user={user.id} is_admin={user.is_admin()} course={course}")
        raise HTTPException(403, "Not authorized")

    meta_path = f"{course_id}/_meta.json"
    data = json.dumps({"items": [i.model_dump() for i in items]}).encode()

    async with httpx.AsyncClient(timeout=30) as client:
        # Delete existing then upload fresh
        await client.request(
            "DELETE",
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}",
            headers={"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY,
                     "Content-Type": "application/json"},
            json={"prefixes": [meta_path]},
        )
        resp = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{meta_path}",
            headers={
                "Authorization": f"Bearer {SERVICE_KEY}",
                "apikey": SERVICE_KEY,
                "Content-Type": "application/json",
                "x-upsert": "true",
            },
            content=data,
        )
        if not resp.is_success:
            raise HTTPException(500, f"Meta save failed: {resp.text}")

    return {"ok": True}


# ── Delete resource ───────────────────────────────────────────
@router.delete("/{course_id}/resources/{resource_id:path}")
async def delete_resource(
    course_id: str,
    resource_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    if not _can_manage(user, course):
        raise HTTPException(403, "Not authorized")

    if resource_id.startswith("file-"):
        filename = resource_id[5:]
        async with httpx.AsyncClient(timeout=30) as client:
            await client.request(
                "DELETE",
                f"{SUPABASE_URL}/storage/v1/object/{BUCKET}",
                headers={"Authorization": f"Bearer {SERVICE_KEY}", "apikey": SERVICE_KEY,
                         "Content-Type": "application/json"},
                json={"prefixes": [f"{course_id}/files/{filename}"]},
            )

    return {"ok": True}
