from __future__ import annotations

import asyncio
import os

from backend.utils.logging import setup_logger
from backend.utils.paths import PathResolver
from backend.core.types import SCENCE_PREVIEW_NAME, SCENCE_VIDEO_NAME, SHOT_VIDEO_NAME
from backend.db.storyboards import get_shot_idxs_by_project_scene, update_scene_composite
from backend.pipeline.config import SessionConfig
from backend.pipeline.events import EventEmitter
from backend.services.video_compositor import VideoCompositor

_logger = setup_logger("pipeline.scene_composite")


async def composite_scene_video(config: SessionConfig, scene: dict, scene_idx: int, emit: EventEmitter) -> None:
    """合成单个场景的视频：将场景下所有 shot video 合成为 composite.mp4，
    并提取第一帧作为 preview.jpg。
    """
    resolver = PathResolver()
    project = resolver.project(config.project_id)
    scene_scope = project.scene(scene_idx)

    shot_idxs = await get_shot_idxs_by_project_scene(config.project_id, scene_idx)
    if not shot_idxs:
        _logger.warning(
            "[scene_compositor] scene=%d no shots found", scene_idx)
        return

    video_paths = []
    for idx in shot_idxs:
        p = scene_scope.shot(idx).path(SHOT_VIDEO_NAME)
        if not os.path.exists(p):
            _logger.warning(
                "[scene_compositor] scene=%d shot=%d video not found, aborting", scene_idx, idx)
            return
        video_paths.append(str(p))

    await emit.emit_progress("scene_compositor", 0, message=f"正在合成场景 {scene_idx} 视频...")

    scene_video_path = scene_scope.path(SCENCE_VIDEO_NAME)
    await asyncio.to_thread(VideoCompositor.compose, video_paths, str(scene_video_path))

    preview_image_path = scene_scope.path(SCENCE_PREVIEW_NAME)
    try:
        await asyncio.to_thread(VideoCompositor.extract_first_frame, str(scene_video_path), str(preview_image_path))
    except Exception as e:
        _logger.error(
            "[scene_compositor] scene=%d extract preview failed: %s", scene_idx, e)
    await update_scene_composite(config.project_id, scene_idx, SCENCE_VIDEO_NAME, SCENCE_PREVIEW_NAME)

    scene_video_url = scene_scope.url(SCENCE_VIDEO_NAME)
    scene_preview_url = scene_scope.url(SCENCE_PREVIEW_NAME)
    await emit.project_updated()

    await emit.emit_progress("scene_compositor", 1, message=f"场景 {scene_idx} 视频合成完成")
