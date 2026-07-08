"""Shared types for the pipeline coordination package."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Optional


# ── Resource name constants ──────────────────────────────────────────

START_FRAME = "start_frame.png"
END_FRAME = "end_frame.png"
SHOT_VIDEO = "shot_video"
SCENE_PREVIEW_VIDEO = "scene_preview_video"
PROJECT_COMPOUND_VIDEO = "project_compound_video"
SCENE_VIDEO = "scene_video"
FINAL_VIDEO = "final_video"


# ── Type aliases ─────────────────────────────────────────────────────

ShotKey = tuple[int, int, int]   # (project_id, scene_idx, shot_id)
SceneKey = tuple[int, int]       # (project_id, scene_idx)
ProjectKey = int                  # project_id


# ── Stage identification ────────────────────────────────────────────

STAGE_DEFAULT_TIMEOUT: float = 600.0  # 10 minutes


@dataclass(frozen=True)
class StageKey:
    """Uniquely identifies a stage in the pipeline.

    Each shot has three stages (start_frame, end_frame, shot_video);
    each scene and project has one stage each.
    """
    project_id: int
    scene_idx: int
    shot_id: int = -1
    resource: str = ""

    def __str__(self) -> str:
        return f"p{self.project_id}s{self.scene_idx}shot{self.shot_id}/{self.resource}"


# ── Stage status lifecycle ───────────────────────────────────────────

class StageStatus(IntEnum):
    """Lifecycle of a single pipeline stage.

    Every resource (start_frame, end_frame, shot_video, …) transitions
    through these states::

        PENDING → CREATING → COMPLETE
        PENDING → STALE → PENDING (recycle)
    """
    PENDING = 0
    CREATING = 1
    COMPLETE = 2
    STALE = 3


# ── Error types ──────────────────────────────────────────────────────

class CoordinatorError(Exception):
    """Base error for the coordination layer."""


class SceneNotRegisteredError(CoordinatorError):
    """The requested scene has not been registered."""


class ProjectNotRegisteredError(CoordinatorError):
    """The requested project has not been registered."""


# ── Payload ──────────────────────────────────────────────────────────

@dataclass
class ArtifactRef:
    """References to a generated artifact (video + optional preview)."""
    video_path: str = ""
    preview_url: str = ""
    video_url: str = ""
