"""Status enums shared across pipeline and DB layers."""

from __future__ import annotations

from enum import Enum


class PipelineStatus(str, Enum):
    """Pipeline / step status values."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PENDING = "pending"
    SKIPPED = "skipped"


class AssetStatus(str, Enum):
    """Asset generation status shared across images, portraits, and videos."""
    WAITING = "waiting"
    GENERATING = "generating"
    GENERATED = "generated"
    ERROR = "error"
    COMPLETED = "completed"
