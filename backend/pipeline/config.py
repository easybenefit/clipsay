"""Re-exports of shared pipeline types.

The canonical definitions live in `backend.core.types`. This module is kept
to preserve existing import paths within the pipeline package.
"""

from backend.db._enums import PipelineStatus
from backend.core.types import (
    COMPOSITE_VIDEO_NAME,
    FINAL_VIDEO_NAME,
    FINAL_PREVIEW_NAME,
    SessionConfig,
    STEP_NAMES,
    Step,
)


def scene_requirement(duration: int) -> str:
    """返回场次数约束（供 story / scene_scripts 步骤使用）。"""
    mapping = {
        5: "场次总数不超过1场",
        10: "场次总数不超过2场",
        12: "场次总数不超过2场",
        15: "场次总数不超过3场",
    }
    return mapping.get(duration, "")


def shot_requirement(duration: int) -> str:
    """返回镜头数约束（供 storyboard 步骤使用）。"""
    mapping = {
        5: "每场镜头数不超过2个",
        10: "每场镜头数不超过3个",
        12: "每场镜头数不超过4个",
        15: "每场镜头数不超过5个",
    }
    return mapping.get(duration, "")


__all__ = ["SessionConfig", "STEP_NAMES", "Step", "PipelineStatus", "scene_requirement", "shot_requirement"]
