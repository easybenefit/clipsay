"""Clipsay image-output wrapper.

Carries the generator's payload in one of four formats (``b64``,
``url``, ``pil``, ``np``) and persists it to disk on demand.  The
:meth:`ImageOutput.save` method dispatches to the right encoder based
on ``fmt``.
"""

from __future__ import annotations

import base64
from typing import Literal, Optional, Union

import cv2
from PIL import Image

from utils.image_io import download_image


class ImageOutput:
    """A single generated image, ready to be persisted to disk."""

    fmt: Literal["b64", "url", "pil", "np"]
    ext: str = "png"
    data: Union[str, Image.Image]
    source_url: Optional[str] = None

    def __init__(
        self,
        fmt: Literal["b64", "url", "pil", "np"],
        ext: str,
        data: Union[str, Image.Image],
        source_url: Optional[str] = None,
    ):
        self.fmt = fmt
        self.ext = ext
        self.data = data
        self.source_url = source_url

    def save_b64(self, path: str) -> None:
        """Decode the base64 payload and write it to ``path``."""
        with open(path, "wb") as f:
            f.write(base64.b64decode(self.data))

    def save_url(self, path: str) -> None:
        """Download the remote URL and write the file to ``path``."""
        download_image(self.data, path)

    def save_pil(self, path: str) -> None:
        """Save a PIL image to ``path``."""
        self.data.save(path)

    def save_np(self, path: str) -> None:
        """Encode a numpy array as PNG and write it to ``path``."""
        cv2.imencode(".png", self.data)[1].tofile(path)

    def save(self, path: str) -> None:
        """Persist the image to ``path`` using the encoder that matches ``fmt``.

        If ``source_url`` is set, a sibling ``.url`` file is written with the
        origin URL so downstream tools can re-fetch the original if needed.
        """
        save_func = getattr(self, f"save_{self.fmt}")
        save_func(path)
        if self.source_url:
            with open(path + ".url", "w") as f:
                f.write(self.source_url)
