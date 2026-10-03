from pathlib import Path

from fastapi import HTTPException, UploadFile, status

DEFAULT_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt", ".csv", ".doc", ".docx"}


async def validate_upload(file: UploadFile, *, allowed_extensions: set[str] | None = None, max_size_bytes: int | None = None) -> bytes:
    if not file or not getattr(file, "filename", None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")
    extension = Path(file.filename).suffix.lower()
    allowed = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
    if extension not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    content = await file.read()
    if max_size_bytes is not None and len(content) > max_size_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum allowed size")
    signatures = {
        ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
        ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
        ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
        ".gif": ((b"GIF87a", b"GIF89a"), "image/gif"),
        ".pdf": (b"%PDF-", "application/pdf"),
        ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/msword"),
        ".docx": (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }
    expected = signatures.get(extension)
    if expected:
        signature, detected_mime = expected
        valid_signature = content.startswith(signature) if isinstance(signature, bytes) else any(content.startswith(item) for item in signature)
        if not valid_signature:
            raise HTTPException(status_code=400, detail="Uploaded content does not match the file extension")
        accepted_mimes = {detected_mime, "application/octet-stream"}
        if extension in {".jpg", ".jpeg"}:
            accepted_mimes.add("image/jpg")
        if file.content_type and file.content_type not in accepted_mimes:
            raise HTTPException(status_code=400, detail="MIME type does not match the uploaded content")
    elif extension in {".txt", ".csv"}:
        if b"\x00" in content:
            raise HTTPException(status_code=400, detail="Text file contains invalid binary content")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Text file must be UTF-8 encoded") from exc
        accepted_mimes = {"text/plain", "text/csv", "application/csv", "application/octet-stream"}
        if file.content_type and file.content_type not in accepted_mimes:
            raise HTTPException(status_code=400, detail="MIME type does not match the uploaded content")
    return content


def safe_storage_name(filename: str) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix.lower()
    return f"{stem}_{abs(hash(filename))}{suffix}"
