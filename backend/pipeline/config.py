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


def duration_requirement(duration: int) -> str:
    """根据视频时长（秒）返回对应的场次/镜头数约束描述，供 LLM prompt 使用。"""
    mapping = {
        5: "场次总数不超过1场，每场镜头数不超过2个。",
        10: "场次总数不超过2场，每场镜头数不超过3个。",
        12: "场次总数不超过2场，每场镜头数不超过4个。",
        15: "场次总数不超过3场，每场镜头数不超过5个。",
    }
    return mapping.get(duration, "")


__all__ = ["SessionConfig", "STEP_NAMES", "Step", "PipelineStatus", "duration_requirement"]
