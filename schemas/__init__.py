"""Clipsay data models (Pydantic v2).

All cross-module data shapes live here.  The Clipsay pipeline code is
typed against these models end-to-end, which keeps the LLM-driven
agents honest about what they emit and the renderer / assembly code
honest about what it consumes.
"""

from .camera_setup import CameraSetup
from .characters import CharacterInEvent, CharacterInNovel, CharacterInScene
from .clip import Clip, ClipStore
from .environment import EnvironmentInScene
from .event import Event
from .frame import Frame
from .image_output import ImageOutput
from .scene import Scene
from .shot_brief import ShotBrief
from .shot_spec import ShotSpec
from .video_output import VideoOutput

__all__ = [
    "CameraSetup",
    "CharacterInEvent",
    "CharacterInNovel",
    "CharacterInScene",
    "Clip",
    "ClipStore",
    "EnvironmentInScene",
    "Event",
    "Frame",
    "ImageOutput",
    "Scene",
    "ShotBrief",
    "ShotSpec",
    "VideoOutput",
]
