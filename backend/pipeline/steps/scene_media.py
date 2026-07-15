from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List

from backend.utils.logging import setup_logger
from backend.pipeline.conductor import get_conductor
from backend.pipeline.frame_generator import FrameGenerator
from backend.pipeline.config import SessionConfig
from backend.pipeline.events import EventEmitter
from backend.schemas.models import ModelConfig

if TYPE_CHECKING:
    from backend.schemas.camera import CameraNode
    from backend.schemas.character import CharacterRead
    from backend.schemas.shot_spec import ShotSpec
    from backend.utils.paths import SceneScope
    from backend.pipeline.conductor import PipelineConductor

logger = setup_logger("scene_media")


async def _generate_camera_frames(
    frame_generator: "FrameGenerator",
    camera: "CameraNode",
    shot_specs: List["ShotSpec"],
    characters: List["CharacterRead"],
    conductor: "PipelineConductor",
    scene: "SceneScope",
) -> None:
    """Generate all start/end frames for every shot in *camera*."""
    shot_idxs = camera.active_shot_idxs
    logger.info("[cam=%d] generating frames for %d shots: %s",
                camera.idx, len(shot_idxs), shot_idxs)

    # ── First shot: first_shot_frame + end_frame ──
    logger.info("[cam=%d shot=%d] queuing first_shot_frame + end_frame",
                camera.idx, shot_idxs[0])
    coros = [
        frame_generator.generate_first_shot_frame(
            camera=camera, shot_specs=shot_specs,
            characters=characters, conductor=conductor, scene=scene,
        ),
        frame_generator.generate_end_frame(
            camera=camera, shot_spec=shot_specs[shot_idxs[0]],
            characters=characters, conductor=conductor, scene=scene,
        ),
    ]

    # ── Remaining shots: start_frame + end_frame for each ──
    for shot_idx in shot_idxs[1:]:
        logger.info("[cam=%d shot=%d] queuing start_frame + end_frame",
                    camera.idx, shot_idx)
        coros.append(frame_generator.generate_start_frame(
            camera=camera, shot_spec=shot_specs[shot_idx],
            characters=characters, conductor=conductor, scene=scene,
        ))
        coros.append(frame_generator.generate_end_frame(
            camera=camera, shot_spec=shot_specs[shot_idx],
            characters=characters, conductor=conductor, scene=scene,
        ))

    logger.info("[cam=%d] awaiting %d frame generation tasks",
                camera.idx, len(coros))
    await asyncio.gather(*coros)
    logger.info("[cam=%d] all frame generation tasks completed", camera.idx)


async def generate_scene_frames(
    frame_generator: "FrameGenerator",
    camera_tree: List["CameraNode"],
    shot_specs: List["ShotSpec"],
    characters: List["CharacterRead"],
    scene: "SceneScope",
) -> None:
    """Generate frames for every camera in *camera_tree* concurrently."""
    logger.info("[scene=%s] generating frames for %d cameras",
                scene.scene_idx, len(camera_tree))
    await asyncio.gather(*[
        _generate_camera_frames(
            frame_generator=frame_generator, camera=cam,
            shot_specs=shot_specs, characters=characters,
            conductor=get_conductor(), scene=scene,
        )
        for cam in camera_tree
    ])
    logger.info(
        "[scene=%s] all camera frame generation completed", scene.scene_idx)


async def generate_scene_videos(
    video_config: ModelConfig,
    project_id: int,
    shot_specs: List["ShotSpec"],
    scene: "SceneScope",
    emit: Optional["EventEmitter"] = None,
) -> None:
    """Generate videos for all shots in a scene concurrently."""
    from backend.pipeline.steps.shot_video import generate_shot_video

    if not shot_specs:
        logger.info(
            "[scene=%s] no shot descriptions, skipping video generation", scene.scene_idx)
        return

    logger.info("[scene=%s] generating videos for %d shots",
                scene.scene_idx, len(shot_specs))
    await asyncio.gather(*[
        generate_shot_video(
            config=video_config, project_id=project_id,
            shot_description=sd, conductor=get_conductor(), scene=scene, emit=emit,
        )
        for sd in shot_specs
    ])
    logger.info("[scene=%s] all shot video generation completed",
                scene.scene_idx)


async def generate_scene_frames_and_videos(
    config: SessionConfig,
    emit: EventEmitter,
    pause_check=None,
) -> dict:
    """Generate frames and videos for ALL scenes in a project concurrently.

    Reads scenes, characters, camera trees, and shot descriptions from
    the database, then dispatches per-scene frame + video generation
    in a single concurrent phase (video generation waits for frames
    internally via the conductor).

    Returns ``{"scene_count": N, "errors": M}``.
    """
    from backend.db.loaders import (
        load_project_data,
        load_shot_descriptions,
        load_camera_tree,
    )
    from backend.utils.paths import PathResolver

    project_id = config.project_id
    frame_generator = FrameGenerator(
        image_config=config.image,
        chat_config=config.chat,
        size=config._get_aspect_size(),
        emit=emit,
    )
    video_config = config.video

    scenes, characters = await load_project_data(project_id)
    resolver = PathResolver()
    errors = 0
    all_tasks = []

    logger.info("[project=%d] generating media for %d scenes",
                project_id, len(scenes))

    conductor = get_conductor()

    for scene in scenes:
        scene_idx = scene["idx"]
        shot_specs = await load_shot_descriptions(project_id, scene_idx)
        if shot_specs is None:
            logger.warning("[project] scene=%d no storyboard found", scene_idx)
            errors += 1
            continue

        camera_tree = await load_camera_tree(project_id, scene_idx)
        if not camera_tree:
            logger.warning(
                "[project] scene=%d no camera tree found", scene_idx)
            errors += 1
            continue

        conductor.register_scene(project_id, scene_idx, shot_specs)

        scene_scope = resolver.project(project_id).scene(scene_idx)

        # Dispatch frame + video generation concurrently per scene.
        # Video generation internally waits for frames via conductor.
        all_tasks.append(
            generate_scene_frames(
                frame_generator=frame_generator,
                camera_tree=camera_tree,
                shot_specs=shot_specs,
                characters=characters,
                scene=scene_scope,
            )
        )
        all_tasks.append(
            generate_scene_videos(
                video_config=video_config,
                project_id=project_id,
                shot_specs=shot_specs,
                scene=scene_scope,
                emit=emit,
            )
        )

    logger.info("[project=%d] awaiting %d concurrent scene tasks (frames + videos)",
                project_id, len(all_tasks))
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    frame_errs = []
    video_errs = []
    for i, r in enumerate(results):
        if not isinstance(r, Exception):
            continue
        if i % 2 == 0:
            frame_errs.append(r)
        else:
            video_errs.append(r)

    if frame_errs:
        logger.error("[project=%d] frame generation failed: %s",
                     project_id, frame_errs[0], exc_info=frame_errs[0])
        raise RuntimeError(
            f"镜头帧生成失败: {frame_errs[0]}"
        )

    for r in video_errs:
        logger.error("[project=%d] video generation failed: %s",
                     project_id, r, exc_info=r)

    if video_errs:
        raise RuntimeError(
            f"{len(video_errs)}/{len(all_tasks) // 2} 场景视频生成失败，首个错误: {video_errs[0]}"
        )

    # ── Compose scene-level videos from shot videos ──
    from backend.pipeline.composite.scene import composite_scene_video
    for scene in scenes:
        scene_idx = scene["idx"]
        try:
            await composite_scene_video(config, scene, scene_idx, emit)
        except Exception as e:
            logger.error(
                "[project=%d] scene=%d composite failed: %s",
                project_id, scene_idx, e, exc_info=e,
            )
            raise RuntimeError(f"场景 {scene_idx} 视频合成失败: {e}")

    logger.info("[project=%d] shot_frames step complete", project_id)
