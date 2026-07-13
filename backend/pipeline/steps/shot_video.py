from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, List, Optional

from backend.clients.video import Video
from backend.utils.logging import setup_logger
from backend.pipeline.conductor import (
    START_FRAME,
    END_FRAME,
    SHOT_VIDEO,
    StageStatus,
    get_conductor,
)
from backend.core.types import SHOT_PREVIEW_NAME, SHOT_VIDEO_NAME, SCENCE_VIDEO_NAME
from backend.schemas.models import ModelConfig
from backend.db.storyboards import get_shot_by_project_scene, update_shot
from backend.services.video_compositor import VideoCompositor

if TYPE_CHECKING:
    from backend.pipeline.events import EventEmitter
    from backend.schemas.shot_spec import ShotSpec
    from backend.pipeline.conductor import PipelineConductor
    from backend.utils.paths import SceneScope

logger = setup_logger("shot_video_step")


async def _persist_and_complete(
    conductor: "PipelineConductor",
    project_id: int,
    scene_idx: int,
    shot_idx: int,
    scene: "SceneScope",
    video_path: str,
    emit: Optional["EventEmitter"] = None,
) -> str:
    shot_scope = scene.shot(shot_idx)

    video_preview_url = ""
    try:
        preview_filename = "video_preview.jpg"
        await asyncio.to_thread(
            VideoCompositor.extract_first_frame, str(video_path),
            str(shot_scope.path(preview_filename)),
        )
        video_preview_url = shot_scope.url(preview_filename)
    except Exception as e:
        logger.warning(
            "Failed to extract video preview for shot %d: %s", shot_idx, e)

    video_url = shot_scope.url(SHOT_VIDEO_NAME)
    await update_shot(project_id, scene_idx, shot_idx, shot_video_url=video_url, video_status="completed")
    if video_preview_url:
        await update_shot(project_id, scene_idx, shot_idx, shot_preview_url=video_preview_url)

    await conductor.change_stage(
        project_id, scene_idx, shot_idx, SHOT_VIDEO, StageStatus.COMPLETE,
        path=str(video_path),
        video_url=shot_scope.url(SHOT_VIDEO_NAME),
    )
    logger.info("[video] shot=%d persisted, preview=%s",
                shot_idx, bool(video_preview_url))
    if emit:
        await emit.project_data_changed()
    return video_preview_url


async def _wait_frames(
    conductor: "PipelineConductor",
    project_id: int,
    scene_idx: int,
    shot_idx: int,
) -> None:
    logger.info("[video] shot=%d waiting for start_frame + end_frame...", shot_idx)
    await asyncio.gather(
        conductor.stages.wait(project_id, scene_idx, shot_idx, START_FRAME),
        conductor.stages.wait(project_id, scene_idx, shot_idx, END_FRAME),
    )
    logger.info("[video] shot=%d start_frame + end_frame ready", shot_idx)


async def generate_shot_video(
    config: ModelConfig,
    project_id: int,
    shot_description: "ShotSpec",
    conductor: "PipelineConductor",
    scene: "SceneScope",
    emit: Optional["EventEmitter"] = None,
) -> None:
    shot_idx = shot_description.idx
    scene_idx = scene.scene_idx
    shot_scope = scene.shot(shot_idx)
    video_path = shot_scope.path(SHOT_VIDEO_NAME)

    if os.path.exists(video_path):
        logger.info("[video] shot=%d skipped, already exists: %s",
                    shot_idx, video_path)
        await _persist_and_complete(conductor, project_id, scene_idx, shot_idx, scene, str(video_path), emit=emit)
        return str(video_path)

    if emit:
        await emit.project_data_changed()

    await _wait_frames(conductor, project_id, scene_idx, shot_idx)

    shot_db = await get_shot_by_project_scene(project_id, scene_idx, shot_idx)
    ref_urls = [
        shot_db.get("start_frame_url", ""),
        shot_db.get("end_frame_url", ""),
    ] if shot_db else []
    missing = [k for k, v in [("start_frame", ref_urls[0]), ("end_frame", ref_urls[1])] if not v]
    if missing:
        raise RuntimeError(
            f"shot={shot_idx} missing frame(s) after _wait_frames: {', '.join(missing)}"
        )
    prompt = (shot_description.motion_desc or "") + \
        "\n" + (shot_description.audio_desc or "")
    logger.info("[video] shot=%d generating, prompt_len=%d, refs=%d",
                shot_idx, len(prompt), len(ref_urls))

    payload = {
        "prompt": prompt,
        "extra_body": {"image": ref_urls},
        "save_path": str(video_path),
    }
    await Video.generate(
        config.model, payload, config.api_key, config.base_url,
        project_id=project_id,
        task_id=f"scene-{scene_idx}-shot-{shot_idx}-video",
        rpm=config.rate_limit_min,
        rpd=config.rate_limit_day,
    )

    if not os.path.exists(str(video_path)) or os.path.getsize(str(video_path)) == 0:
        logger.error(
            "[video] shot=%d video file missing after generation: %s",
            shot_idx, video_path,
        )
        raise RuntimeError(f"video file missing after generation: {video_path}")

    VideoCompositor.extract_first_frame(
        str(video_path), shot_scope.path(SHOT_PREVIEW_NAME))
    await _persist_and_complete(conductor, project_id, scene_idx, shot_idx, scene, str(video_path), emit=emit)
    logger.info("[video] shot=%d done", shot_idx)


async def generate_scene_shot_videos(
    config: ModelConfig,
    project_id: int,
    shot_descriptions: List["ShotSpec"],
    scene: "SceneScope",
    emit: Optional["EventEmitter"] = None,
) -> None:
    if not shot_descriptions:
        return

    video_tasks = [
        generate_shot_video(
            config=config,
            project_id=project_id,
            shot_description=sd,
            conductor=get_conductor(),
            scene=scene,
            emit=emit,
        )
        for sd in shot_descriptions
    ]
    await asyncio.gather(*video_tasks)


async def compose_scene_video(
    project_id: int,
    scene_idx: int,
    shot_descriptions: List["ShotSpec"],
    scene: "SceneScope",
) -> None:
    video_paths = []
    for sd in shot_descriptions:
        p = scene.shot(sd.idx).path(SHOT_VIDEO_NAME)
        if p.exists():
            video_paths.append(str(p))

    if not video_paths:
        logger.warning(
            "[video] scene=%d no shot videos found, skipping compose", scene_idx)
        return

    scene_video_path = scene.path(SCENCE_VIDEO_NAME)
    await asyncio.to_thread(VideoCompositor.compose, video_paths, str(scene_video_path))
    logger.info("[video] scene=%d composite done: %s",
                scene_idx, scene_video_path)
