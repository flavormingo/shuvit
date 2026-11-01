import uuid
from pathlib import Path

import asyncio
from PIL import Image

from app.config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}
THUMBNAIL_WIDTH = 400


def _get_media_dir(park_id: str) -> Path:
    media_dir = Path(settings.MEDIA_DIR) / park_id
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


async def save_upload(
    file_bytes: bytes, content_type: str, park_id: str
) -> tuple[str, str | None]:
    """Save uploaded file and return (file_url, thumbnail_url)."""
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }
    ext = ext_map.get(content_type, ".bin")
    file_id = str(uuid.uuid4())
    media_dir = _get_media_dir(park_id)

    file_path = media_dir / f"{file_id}{ext}"
    file_path.write_bytes(file_bytes)

    file_url = f"/media/{park_id}/{file_id}{ext}"
    thumbnail_url = None

    if content_type in ALLOWED_IMAGE_TYPES:
        thumbnail_url = await asyncio.to_thread(
            _generate_thumbnail, file_path, media_dir, file_id
        )

    return file_url, thumbnail_url


def _generate_thumbnail(file_path: Path, media_dir: Path, file_id: str) -> str:
    thumb_path = media_dir / f"{file_id}_thumb.jpg"
    with Image.open(file_path) as img:
        ratio = THUMBNAIL_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((THUMBNAIL_WIDTH, new_height), Image.LANCZOS)
        img = img.convert("RGB")
        img.save(thumb_path, "JPEG", quality=85)
    return f"/media/{media_dir.name}/{file_id}_thumb.jpg"


# Magic bytes for file type verification
_MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # RIFF....WEBP
    b"\x00\x00\x00": "video/mp4",  # ftyp box (offset 4)
}


def _verify_magic_bytes(file_bytes: bytes, content_type: str) -> bool:
    """Verify file content matches claimed content type."""
    if content_type == "image/jpeg":
        return file_bytes[:3] == b"\xff\xd8\xff"
    if content_type == "image/png":
        return file_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    if content_type == "image/webp":
        return file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP"
    if content_type in ("video/mp4", "video/quicktime"):
        return file_bytes[4:8] == b"ftyp" or file_bytes[4:8] == b"moov"
    return False


def validate_upload(content_type: str, size: int, file_bytes: bytes | None = None) -> str | None:
    """Return error message if invalid, None if ok."""
    all_allowed = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES
    if content_type not in all_allowed:
        return f"Unsupported file type: {content_type}"
    if content_type in ALLOWED_IMAGE_TYPES and size > settings.MAX_IMAGE_SIZE:
        return f"Image too large. Max {settings.MAX_IMAGE_SIZE // (1024*1024)} MB."
    if content_type in ALLOWED_VIDEO_TYPES and size > settings.MAX_VIDEO_SIZE:
        return f"Video too large. Max {settings.MAX_VIDEO_SIZE // (1024*1024)} MB."
    if file_bytes and not _verify_magic_bytes(file_bytes, content_type):
        return "File content does not match declared type"
    return None
