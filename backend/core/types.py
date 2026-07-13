"""Shared domain types used across pipeline, agents, and core modules."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image

from backend.schemas import FrameRecord
from backend.schemas.models import ModelConfig
from backend.db._enums import PipelineStatus, AssetStatus


@dataclass
class ImageRef:
    """A reference to a generated image with its metadata."""
    identifier: str = ""
    url: str = ""       # Remote API URL (used for side/back reference images)
    prompt: str = ""
    local_url: str = ""  # Frontend-accessible local serving path


STEP_NAMES = [
    "story", "characters", "portraits",
    "scene_scripts", "storyboard",
    "shot_frames", "composite_video",
]


# ── Portrait view constants ─────────────────────────────────────────

VIEW_FRONT = "front"
VIEW_SIDE = "side"
VIEW_BACK = "back"
PARALLEL_VIEWS = (VIEW_SIDE, VIEW_BACK)


# ── Portrait status constants (bit-field values for attributes.portrait_status) ──

PORTRAIT_STATUS_GENERATING = 1
PORTRAIT_STATUS_GENERATED = 2
PORTRAIT_STATUS_ERROR = 3


class Step(str, Enum):
    """Pipeline step name constants."""
    STORY = "story"
    CHARACTERS = "characters"
    PORTRAITS = "portraits"
    SCENE_SCRIPTS = "scene_scripts"
    STORYBOARD = "storyboard"
    SHOT_FRAMES = "shot_frames"
    COMPOSITE_VIDEO = "composite_video"

    PROGRESS_START = 0.0
    PROGRESS_DONE = 1.0


# ── Standard filenames for generated assets ──
SHOT_VIDEO_NAME = "shot_video.mp4"
SCENCE_VIDEO_NAME = "scence_video.mp4"
COMPOSITE_VIDEO_NAME = "composite_video.mp4"
NEW_IDEA_VIDEO_NAME = "new_idea_video.mp4"
FINAL_VIDEO_NAME = "final_video.mp4"

SHOT_PREVIEW_NAME = "shot_video.png"
SCENCE_PREVIEW_NAME = "scence_video.png"
NEW_IDEA_PREVIEW_NAME = "new_idea_video.png"
FINAL_PREVIEW_NAME = "final_preview.png"


@dataclass
class SessionConfig:
    project_id: int
    idea: str = ""
    style: str = "realistic"
    size: str = "16:9"
    resolution: str = "720p"
    duration: int = 10
    frame_rate: int = 24
    language: str = "zh"

    # Model endpoints — each is a (model, api_key, base_url, rate limit) tuple.
    chat: ModelConfig = field(default_factory=lambda: ModelConfig(rate_limit_min=50, rate_limit_day=2000))
    image: ModelConfig = field(default_factory=lambda: ModelConfig(rate_limit_min=10, rate_limit_day=500))
    video: ModelConfig = field(default_factory=lambda: ModelConfig(rate_limit_min=1, rate_limit_day=1000))

    @classmethod
    async def from_db(cls, project_id: int) -> "SessionConfig":
        from backend.db.projects import load_session_config
        return await load_session_config(project_id)

    def _get_resolution_size(self) -> str:
        mapping = {
            "480p": "854x480",
            "720p": "1280x720",
            "1080p": "1920x1920",
        }
        return mapping.get(self.resolution, "1280x720")

    def _get_aspect_size(self) -> str:
        aspect_map = {
            "16:9": "1280x720",
            "9:16": "720x1280",
            "1:1": "1024x1024",
        }
        return aspect_map.get(self.size, "1280x720")

    @property
    def project_root(self) -> Path:
        from backend.db import PathResolver_root as _PR_ROOT
        return _PR_ROOT() / f"proj_{self.project_id}"

    @property
    def portraits_dir(self) -> Path:
        return self.project_root / "portraits"

    @property
    def project_dir(self) -> Path:
        return self.project_root

    @property
    def static_prefix(self) -> str:
        return f"/local/proj_{self.project_id}"

    @property
    def scenes_base(self) -> Path:
        return self.project_root / "scenes"

    def scene_dir(self, scene_idx: int) -> Path:
        return self.scenes_base / str(scene_idx)

    def scene_composite_path(self, scene_idx: int) -> Path:
        return self.scene_dir(scene_idx) / "composite.mp4"

    def scene_preview_path(self, scene_idx: int) -> Path:
        return self.scene_dir(scene_idx) / "preview.jpg"

    @property
    def final_video_path(self) -> Path:
        return self.project_root / FINAL_VIDEO_NAME

    @property
    def final_preview_path(self) -> Path:
        return self.project_root / FINAL_PREVIEW_NAME


class VideoOutput:
    """Simple data holder for transition video generation output."""
    def __init__(self, fmt: str, ext: str, data: str):
        self.fmt = fmt
        self.ext = ext
        self.data = data


class ImageOutput:
    """Simple data holder for transition video frame extraction output."""
    def __init__(self, fmt: str, ext: str, data: Image.Image):
        self.fmt = fmt
        self.ext = ext
        self.data = data

    def save(self, path: str) -> None:
        self.data.save(path)
