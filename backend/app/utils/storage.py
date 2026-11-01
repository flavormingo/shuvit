"""Validates, sanitizes and stores uploaded media.

The file's type is worked out from its bytes, never from what the client claims.
Images are re-encoded to JPEG and videos are remuxed, which also strips EXIF and
GPS metadata so a public photo can't reveal where someone took it.
"""

import asyncio
import io
import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)

pillow_heif.register_heif_opener()
Image.MAX_IMAGE_PIXELS = 60_000_000

MAX_IMAGE_DIMENSION = 2048
THUMBNAIL_WIDTH = 400
AVATAR_SIZE = 512
FFMPEG_TIMEOUT_SECONDS = 120

_HEIF_BRANDS = {
    b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1", b"avif",
}


class InvalidUpload(Exception):
    """The upload can't be accepted. The message is safe to show to the user."""


@dataclass
class StoredMedia:
    media_type: str
    file_url: str
    thumbnail_url: str | None


def sniff_media_type(data: bytes) -> str | None:
    """Return 'image' or 'video' based on file content, or None if unsupported."""
    if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image"
    if data[4:8] == b"ftyp":
        return "image" if data[8:12] in _HEIF_BRANDS else "video"
    if data[4:8] == b"moov":
        return "video"
    return None


def _check_size(media_type: str, size: int) -> None:
    limit = settings.MAX_IMAGE_SIZE if media_type == "image" else settings.MAX_VIDEO_SIZE
    if size > limit:
        raise InvalidUpload(f"{media_type.capitalize()} too large. Max {limit // (1024 * 1024)} MB.")


def _open_image(data: bytes) -> Image.Image:
    """Decode to upright RGB. Transparent areas become white."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = ImageOps.exif_transpose(source)
            if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                flattened = Image.new("RGB", rgba.size, "white")
                flattened.paste(rgba, mask=rgba.getchannel("A"))
                return flattened
            return image.convert("RGB")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise InvalidUpload("That image couldn't be read.") from exc


def _encode_jpeg(image: Image.Image, max_width: int, max_height: int) -> bytes:
    copy = image.copy()
    copy.thumbnail((max_width, max_height), Image.LANCZOS)
    output = io.BytesIO()
    copy.save(output, "JPEG", quality=85, optimize=True)
    return output.getvalue()


def _process_image(data: bytes) -> tuple[bytes, bytes]:
    image = _open_image(data)
    return (
        _encode_jpeg(image, MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
        _encode_jpeg(image, THUMBNAIL_WIDTH, THUMBNAIL_WIDTH * 4),
    )


def _process_avatar(data: bytes) -> bytes:
    image = ImageOps.fit(_open_image(data), (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    return _encode_jpeg(image, AVATAR_SIZE, AVATAR_SIZE)


def _process_video(data: bytes) -> tuple[bytes, bytes]:
    """Remux to faststart MP4 without metadata, and grab a thumbnail frame."""
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg is not installed; can't process video uploads")
        raise InvalidUpload("Video uploads aren't available right now.")

    base = ["ffmpeg", "-nostdin", "-loglevel", "error", "-protocol_whitelist", "file", "-f", "mov"]

    with tempfile.TemporaryDirectory() as tmp:
        source, video, thumb = (Path(tmp) / name for name in ("in.mov", "out.mp4", "thumb.jpg"))
        source.write_bytes(data)
        commands = [
            [*base, "-i", str(source), "-map", "0:v:0", "-map", "0:a?", "-c", "copy",
             "-map_metadata", "-1", "-map_chapters", "-1", "-movflags", "+faststart", str(video)],
            [*base, "-i", str(source), "-frames:v", "1", "-vf", f"scale={THUMBNAIL_WIDTH}:-2",
             "-map_metadata", "-1", str(thumb)],
        ]
        try:
            for command in commands:
                subprocess.run(command, check=True, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise InvalidUpload("That video couldn't be read.") from exc
        return video.read_bytes(), thumb.read_bytes()


def _media_dir(folder: str) -> Path:
    path = Path(settings.MEDIA_DIR) / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(folder: str, name: str, data: bytes) -> str:
    (_media_dir(folder) / name).write_bytes(data)
    return f"/media/{folder}/{name}"


async def store_media(data: bytes, folder: str) -> StoredMedia:
    media_type = sniff_media_type(data)
    if media_type is None:
        raise InvalidUpload("Unsupported file type. Please choose a photo.")
    if media_type == "video" and not settings.ALLOW_VIDEO_UPLOADS:
        raise InvalidUpload("Only photos can be uploaded right now.")
    _check_size(media_type, len(data))

    file_id = uuid.uuid4()
    if media_type == "image":
        full, thumb = await asyncio.to_thread(_process_image, data)
        extension = ".jpg"
    else:
        full, thumb = await asyncio.to_thread(_process_video, data)
        extension = ".mp4"

    return StoredMedia(
        media_type=media_type,
        file_url=_write(folder, f"{file_id}{extension}", full),
        thumbnail_url=_write(folder, f"{file_id}_thumb.jpg", thumb),
    )


async def store_avatar(data: bytes) -> str:
    if sniff_media_type(data) != "image":
        raise InvalidUpload("Avatars must be a photo.")
    _check_size("image", len(data))
    avatar = await asyncio.to_thread(_process_avatar, data)
    return _write("avatars", f"{uuid.uuid4()}.jpg", avatar)


def delete_media_file(url: str | None) -> None:
    """Remove a stored file by URL. Refuses anything outside MEDIA_DIR."""
    if not url or not url.startswith("/media/"):
        return
    root = Path(settings.MEDIA_DIR).resolve()
    path = (root / url.removeprefix("/media/")).resolve()
    if path.is_relative_to(root) and path.is_file():
        path.unlink()
