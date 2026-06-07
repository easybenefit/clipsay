"""Clipsay video-output wrapper.

Carries the generator's payload as either a remote URL or raw bytes and
persists it to disk on demand.
"""

from __future__ import annotations

from typing import Literal, Union

from utils.video_io import download_video


class VideoOutput:
    """A single generated video, ready to be persisted to disk."""

    fmt: Literal["url", "bytes"]
    ext: str = "mp4"
    data: Union[str, bytes]

    def __init__(
        self,
        fmt: Literal["url", "bytes"],
        ext: str,
        data: Union[str, bytes],
    ):
        self.fmt = fmt
        self.ext = ext
        self.data = data

    def save_url(self, path: str) -> None:
        """Download and save a video from a remote URL to ``path``."""
        download_video(self.data, path)

    def save_bytes(self, path: str) -> None:
        """Write raw video bytes to ``path``."""
        with open(path, "wb") as f:
            f.write(self.data)

    def save(self, path: str) -> None:
        """Persist the video to ``path`` using the encoder that matches ``fmt``."""
        save_func = getattr(self, f"save_{self.fmt}")
        save_func(path)
