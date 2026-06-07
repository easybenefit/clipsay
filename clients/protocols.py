"""Structural-typing contracts for Clipsay render backends.

A class that exposes the right method signatures satisfies these
protocols — no inheritance required.  New backends (e.g. Veo, Doubao,
local Stable Diffusion) only need to implement the documented method
shape to be drop-in compatible.
"""

from typing import List, Protocol, runtime_checkable

from schemas.image_output import ImageOutput
from schemas.video_output import VideoOutput


@runtime_checkable
class ImageGenerator(Protocol):
    """Generates a single image from a text prompt and optional references."""

    async def generate_single_image(
        self,
        prompt: str,
        reference_image_paths: List[str],
        **kwargs,
    ) -> ImageOutput: ...


@runtime_checkable
class VideoGenerator(Protocol):
    """Generates a single video from a text prompt and optional references."""

    async def generate_single_video(
        self,
        prompt: str,
        reference_image_paths: List[str],
        **kwargs,
    ) -> VideoOutput: ...
