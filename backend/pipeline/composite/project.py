from __future__ import annotations

import asyncio
from pathlib import Path

from backend.utils.logging import setup_logger
from backend.utils.paths import PathResolver
from backend.core.types import SCENCE_VIDEO_NAME, SCENCE_PREVIEW_NAME, NEW_IDEA_PREVIEW_NAME, NEW_IDEA_VIDEO_NAME
from backend.db import update_project_final_video, get_scene_count
from backend.pipeline.config import SessionConfig
from backend.pipeline.events import EventEmitter
from backend.services.video_compositor import VideoCompositor

_logger = setup_logger("pipeline.composite_video")


async def composite_video(config: SessionConfig, emit: EventEmitter) -> None:
    _logger.info("[composite_video] starting, project_id=%d",
                 config.project_id)

    resolver = PathResolver()
    project = resolver.project(config.project_id)

    # 1. Get scene count from DB
    scene_count = await get_scene_count(config.project_id)
    if scene_count == 0:
        _logger.warning("[composite_video] no scenes found, aborting")
        return

    # 2. Collect existing scene composite videos
    scene_video_paths = []
    for i in range(scene_count):
        video_path = project.scene(i).path(SCENCE_VIDEO_NAME)
        if not Path(video_path).exists():
            _logger.warning(
                "[composite_video] scene=%d %s not found, aborting", i, SCENCE_VIDEO_NAME)
            return
        scene_video_paths.append(str(video_path))

    # 3. Emit start notification
    await emit.emit_progress("composite_video", 0, message="开始合成最终视频...")

    # 4. Compose final video
    final_video_path = project.path(NEW_IDEA_VIDEO_NAME)
    final_preview_path = project.path(NEW_IDEA_PREVIEW_NAME)

    await asyncio.to_thread(VideoCompositor.compose, scene_video_paths, final_video_path)

    # 5. Extract preview frame
    try:
        await asyncio.to_thread(VideoCompositor.extract_first_frame, final_video_path, final_preview_path)
    except Exception as e:
        _logger.error("[composite_video] extract preview failed: %s", e)

    # 6. Persist to DB
    final_video_url = project.url(NEW_IDEA_VIDEO_NAME)
    final_preview_url = project.url(NEW_IDEA_PREVIEW_NAME)
    await update_project_final_video(config.project_id, final_video_url, final_preview_url)

    # 7. Emit complete notification
    await emit.project_updated()
    _logger.info("[composite_video] final video saved: %s", final_video_url)
