from fastapi import HTTPException, UploadFile

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


async def validate_and_read(file: UploadFile) -> tuple[bytes, str]:
    """Validate an uploaded file (type + size) and return (bytes, extension).
    Raises HTTPException(400) if the file fails validation."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, "Only PDF, JPG, and PNG files are allowed")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(400, "File exceeds the 20 MB size limit")
    if len(data) == 0:
        raise HTTPException(400, "Uploaded file is empty")

    return data, ALLOWED_CONTENT_TYPES[file.content_type]
