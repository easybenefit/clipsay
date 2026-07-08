"""Pipeline coordination package.

Manages stage lifecycles, stage-gate triggers, pub/sub event dispatch,
and artifact metadata storage for the video generation pipeline.
"""

from __future__ import annotations

from backend.pipeline.conductor._types import (
    START_FRAME,
    END_FRAME,
    SHOT_VIDEO,
    SCENE_PREVIEW_VIDEO,
    PROJECT_COMPOUND_VIDEO,
    SCENE_VIDEO,
    FINAL_VIDEO,
    StageStatus,
    ArtifactRef,
    CoordinatorError,
    SceneNotRegisteredError,
    ProjectNotRegisteredError,
)
from backend.pipeline.conductor.conductor import PipelineConductor
from backend.pipeline.conductor._bus import EventBus
from backend.pipeline.conductor._gate import Gate
from backend.pipeline.conductor._stage_manager import StageManager
from backend.pipeline.conductor._stage import Stage
from backend.pipeline.conductor._vault import ArtifactVault


__all__ = [
    # Resource name constants
    "START_FRAME",
    "END_FRAME",
    "SHOT_VIDEO",
    "SCENE_PREVIEW_VIDEO",
    "PROJECT_COMPOUND_VIDEO",
    "SCENE_VIDEO",
    "FINAL_VIDEO",

    # Types
    "StageStatus",
    "ArtifactRef",
    # Errors
    "CoordinatorError",
    "SceneNotRegisteredError",
    "ProjectNotRegisteredError",
    # Classes
    "PipelineConductor",
    "EventBus",
    "Gate",
    "StageManager",
    "Stage",
    "ArtifactVault",
]


# ── convenience accessor ─────────────────────────────────────────────

def get_conductor() -> PipelineConductor:
    """Return the singleton ``PipelineConductor`` instance."""
    return PipelineConductor.get_instance()
