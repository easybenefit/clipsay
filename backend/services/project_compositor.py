from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image
from moviepy import VideoFileClip

from backend.utils.logging import setup_logger
from backend.utils.paths import PathResolver, normalize_local_url
from backend.core.types import SCENCE_VIDEO_NAME, NEW_IDEA_PREVIEW_NAME, NEW_IDEA_VIDEO_NAME
from backend.db import update_project_final_video, get_scene_ids
from backend.services.video_compositor import VideoCompositor

_logger = setup_logger("project_compositor")


class ProjectCompositor:
    """Compose the final project video from scene composite videos."""

    @staticmethod
    async def compose(project_id: int, force: bool = False) -> dict:
        """Compose final video for a project and persist results.

        When *force* is ``True``, existing output files are removed first
        so the video is always regenerated.

        Returns a dict with ``final_video_url``, ``final_preview_url``,
        and ``actual_duration``.
        """
        resolver = PathResolver()
        project = resolver.project(project_id)

        # 1. Get scene indices from DB
        scene_ids = await get_scene_ids(project_id)
        if not scene_ids:
            raise ValueError("No scenes found")

        # 2. Collect existing scene composite videos
        scene_video_paths = []
        for idx in scene_ids:
            video_path = project.scene(idx).path(SCENCE_VIDEO_NAME)
            if not Path(video_path).exists():
                raise ValueError(
                    f"Scene {idx} video not found: {video_path}")
            scene_video_paths.append(str(video_path))

        # 3. Compose final video
        final_video_path = project.path(NEW_IDEA_VIDEO_NAME)
        final_preview_path = project.path(NEW_IDEA_PREVIEW_NAME)

        if force:
            for p in (final_video_path, final_preview_path):
                if Path(p).exists():
                    Path(p).unlink()

        await asyncio.to_thread(
            VideoCompositor.compose, scene_video_paths, final_video_path)

        # 4. Extract preview frame & read duration (one VideoFileClip load)
        final_video_url = project.url(NEW_IDEA_VIDEO_NAME)
        final_preview_url = project.url(NEW_IDEA_PREVIEW_NAME)
        actual_duration = 0

        try:
            clip = VideoFileClip(final_video_path)
            try:
                frame = clip.get_frame(0)
                await asyncio.to_thread(
                    lambda: Image.fromarray(frame).save(
                        final_preview_path, quality=85)
                )
                actual_duration = int(clip.duration)
            finally:
                clip.close()
        except Exception as e:
            _logger.warning(
                "[composite_video] failed to extract preview/duration: %s", e)

        # 5. Persist to DB
        await update_project_final_video(
            project_id,
            normalize_local_url(final_video_url),
            normalize_local_url(final_preview_url),
            actual_duration,
        )

        _logger.info(
            "[composite_video] final video saved: %s", final_video_url)
        return {
            "final_video_url": final_video_url,
            "final_preview_url": final_preview_url,
            "actual_duration": actual_duration,
        }