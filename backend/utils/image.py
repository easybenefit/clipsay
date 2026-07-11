"""Image utility helpers (base64 encoding, resizing, etc.)."""

import base64
import io
from pathlib import Path

from PIL import Image


def to_filename(identifier: str, view_type: str, image_type: str = 'png') -> str:
    """Build a filename like ``alice_front.png``."""
    safe = identifier.replace("（", "_").replace("）", "_")
    return f"{safe}_{view_type}.{image_type.removeprefix('.')}"


def to_base64(
    image_path: str,
    max_dimension: int = 1024,
    quality: int = 85,
) -> str:
    """Read an image from disk, optionally resize, and return a base64 data URI.

    Args:
        image_path: Path to the image file on disk.
        max_dimension: If the longer side exceeds this, the image is resized
                       proportionally (default 1024).
        quality: JPEG compression quality (1-100, default 85).

    Returns:
        A ``data:image/jpeg;base64,...`` URI string.
    """
    path = Path(image_path)
    img = Image.open(path)

    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    data = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{data}"
