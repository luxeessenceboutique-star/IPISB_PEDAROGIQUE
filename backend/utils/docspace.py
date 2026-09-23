"""Thin client for the ONLYOFFICE DocSpace REST API — used to push a
generated course deck into DocSpace so it can be opened in a *live,
in-platform* editor (see routers/course_generation.py's
/{course_id}/docspace-editor), instead of only ever downloading a static
file. Every call here was verified against the real DocSpace instance
before being written, not guessed from docs alone.
"""
import os

import httpx

DOCSPACE_URL = os.environ.get("DOCSPACE_URL", "").rstrip("/")
DOCSPACE_API_KEY = os.environ.get("DOCSPACE_API_KEY", "")
DOCSPACE_FOLDER_ID = os.environ.get("DOCSPACE_FOLDER_ID", "")

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _headers() -> dict:
    return {"Authorization": f"Bearer {DOCSPACE_API_KEY}"}


def configured() -> bool:
    return bool(DOCSPACE_URL and DOCSPACE_API_KEY and DOCSPACE_FOLDER_ID)


async def upload_deck(filename: str, data: bytes) -> dict:
    """Uploads a .pptx into the shared course-decks DocSpace folder.
    Returns {"id": <file id, str>, "editorUrl": <direct editor page>}."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{DOCSPACE_URL}/api/2.0/files/{DOCSPACE_FOLDER_ID}/upload",
            headers=_headers(),
            files={"file": (filename, data, PPTX_MIME)},
        )
        resp.raise_for_status()
        body = resp.json()["response"]
        row = body[0] if isinstance(body, list) else body
        file_id = str(row["id"])
        return {"id": file_id, "editorUrl": f"{DOCSPACE_URL}/doceditor?fileid={file_id}"}
