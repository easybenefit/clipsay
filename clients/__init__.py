"""Clipsay rendering backends.

This package exposes the structural-typing protocols every image / video
generator must satisfy, the config-driven factory that instantiates them
from a parsed YAML config, and the two concrete backends that are
actually shipped (Agnes image and Agnes video).
"""

from .agnes_image_generator import AgnesImageGenerator
from .agnes_video_generator import AgnesVideoGenerator
from .protocols import ImageGenerator, VideoGenerator
from .render_factory import RenderFactory

__all__ = [
    "AgnesImageGenerator",
    "AgnesVideoGenerator",
    "ImageGenerator",
    "RenderFactory",
    "VideoGenerator",
]
