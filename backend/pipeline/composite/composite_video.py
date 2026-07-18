from __future__ import annotations

from backend.utils.logging import setup_logger
from backend.pipeline.events import EventEmitter
from backend.services.project_compositor import ProjectCompositor

_logger = setup_logger("pipeline.composite_video")


async def composite_project_video(project_id: int) -> dict:
    """Thin wrapper: delegate to ProjectCompositor."""
    return await ProjectCompositor.compose(project_id)


async def composite_video(project_id: int, emit: EventEmitter) -> None:
    """Pipeline entry: compose final video and emit events."""
    _logger.info("[composite_video] starting, project_id=%d", project_id)

    await emit.emit_progress("composite_video", 0, message="开始合成最终视频...")

    try:
        result = await composite_project_video(project_id)
    except Exception as e:
        _logger.error("[composite_video] failed: %s", e)
        return

    await emit.project_data_changed()
    _logger.info("[composite_video] complete: %s", result["final_video_url"])