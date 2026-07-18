from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List

from backend.utils.logging import setup_logger
from backend.pipeline.conductor import get_conductor
from backend.pipeline.frame_generator import FrameGenerator
from backend.pipeline.config import SessionConfig, Step
from backend.pipeline.events import EventEmitter
from backend.schemas.models import ModelConfig

if TYPE_CHECKING:
    from backend.schemas.camera import CameraNode
    from backend.schemas.character import CharacterRead
    from backend.schemas.shot_spec import ShotSpec
    from backend.utils.paths import SceneScope
    from backend.pipeline.conductor import PipelineConductor

logger = setup_logger("scene_media")

_MAX_CONCURRENT_SCENES = 4
_MAX_CONCURRENT_FRAMES_PER_CAM = 6


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

    frame_sem = asyncio.Semaphore(_MAX_CONCURRENT_FRAMES_PER_CAM)

    async def _run_frame(c):
        async with frame_sem:
            return await c

    await asyncio.gather(*[_run_frame(c) for c in coros])
    logger.info("[cam=%d] all frame generation tasks completed", camera.idx)


async def _run_scene_tasks(
    project_id: int,
    frame_generator: "FrameGenerator",
    video_config: ModelConfig,
    camera_tree: List["CameraNode"],
    shot_specs: List["ShotSpec"],
    characters: List["CharacterRead"],
    conductor: "PipelineConductor",
    scene: "SceneScope",
    emit: Optional["EventEmitter"] = None,
    size: str = "",
) -> tuple[int, Exception | None, Exception | None]:
    """Run frame generation and video generation for one scene concurrently.
    Returns (scene_idx, frame_error, video_error).
    """
    scene_idx = scene.scene_idx

    # ── Frame generation ──
    logger.info("[scene=%s] generating frames for %d cameras",
                scene_idx, len(camera_tree))
    frame_coros = [
        _generate_camera_frames(
            frame_generator=frame_generator, camera=cam,
            shot_specs=shot_specs, characters=characters,
            conductor=conductor, scene=scene,
        )
        for cam in camera_tree
    ]

    # ── Video generation ──
    from backend.pipeline.steps.shot_video import generate_shot_video
    logger.info("[scene=%s] generating videos for %d shots",
                scene_idx, len(shot_specs))
    video_coros = [
        generate_shot_video(
            config=video_config, project_id=project_id,
            shot_description=sd, conductor=conductor, scene=scene, emit=emit,
            size=size,
        )
        for sd in shot_specs
    ]

    frame_result, video_result = await asyncio.gather(
        asyncio.gather(*frame_coros),
        asyncio.gather(*video_coros),
        return_exceptions=True,
    )

    frame_err = frame_result if isinstance(frame_result, Exception) else None
    video_err = video_result if isinstance(video_result, Exception) else None

    if frame_err is None:
        logger.info(
            "[scene=%s] all camera frame generation completed", scene_idx)
    if video_err is None:
        logger.info(
            "[scene=%s] all shot video generation completed", scene_idx)

    return scene_idx, frame_err, video_err


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
        size=config.get_image_size(),
        emit=emit,
        ratio=config.size,
    )
    video_config = config.video

    await emit.emit_progress(Step.SHOT_FRAMES, 0.0, message="开始生成镜头画面与视频...")

    scenes, characters = await load_project_data(project_id)
    resolver = PathResolver()
    errors = 0
    valid_scenes = []

    logger.info("[project=%d] generating media for %d scenes",
                project_id, len(scenes))
    await emit.emit_progress(Step.SHOT_FRAMES, 0.05, message=f"已加载 {len(scenes)} 个场景")

    conductor = get_conductor()

    scene_tasks = []

    for scene in scenes:
        scene_idx = scene["idx"]
        shot_specs, camera_tree = await asyncio.gather(
            load_shot_descriptions(project_id, scene_idx),
            load_camera_tree(project_id, scene_idx),
        )
        if shot_specs is None:
            logger.warning("[project] scene=%d no storyboard found", scene_idx)
            errors += 1
            continue

        if not camera_tree:
            logger.warning(
                "[project] scene=%d no camera tree found", scene_idx)
            errors += 1
            continue

        conductor.register_scene(project_id, scene_idx, shot_specs)

        scene_scope = resolver.project(project_id).scene(scene_idx)
        valid_scenes.append(scene)

        scene_tasks.append(
            _run_scene_tasks(
                project_id=project_id,
                frame_generator=frame_generator,
                video_config=video_config,
                camera_tree=camera_tree,
                shot_specs=shot_specs,
                characters=characters,
                conductor=conductor,
                scene=scene_scope,
                emit=emit,
                size=config.get_image_size(),
            )
        )

    await emit.emit_progress(Step.SHOT_FRAMES, 0.1, message=f"正在并发处理 {len(valid_scenes)} 个场景的画面与视频...")

    logger.info("[project=%d] awaiting %d concurrent scene tasks, max_concurrent=%d",
                project_id, len(scene_tasks), _MAX_CONCURRENT_SCENES)

    scene_sem = asyncio.Semaphore(_MAX_CONCURRENT_SCENES)

    async def _run_with_sem(coro):
        async with scene_sem:
            return await coro

    results = await asyncio.gather(
        *[_run_with_sem(t) for t in scene_tasks], return_exceptions=True,
    )

    await emit.emit_progress(Step.SHOT_FRAMES, 0.6, message="画面与视频生成完毕")

    frame_errs = []
    video_errs = []
    for r in results:
        if isinstance(r, Exception):
            frame_errs.append(r)
            continue
        _, frame_err, video_err = r
        if frame_err:
            frame_errs.append(frame_err)
        if video_err:
            video_errs.append(video_err)

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
            f"{len(video_errs)}/{len(valid_scenes)} 场景视频生成失败，首个错误: {video_errs[0]}"
        )

    # ── Compose scene-level videos from shot videos ──
    from backend.pipeline.composite.scene import composite_scene_video

    await emit.emit_progress(Step.SHOT_FRAMES, 0.65, message=f"正在合成 {len(valid_scenes)} 个场景视频...")
    composite_results = await asyncio.gather(*[
        composite_scene_video(config, scene, scene["idx"], emit)
        for scene in valid_scenes
    ], return_exceptions=True)

    composite_errs = []
    for scene, r in zip(valid_scenes, composite_results):
        if isinstance(r, Exception):
            composite_errs.append((scene["idx"], r))
            logger.error(
                "[project=%d] scene=%d composite failed: %s",
                project_id, scene["idx"], r, exc_info=r,
            )

    if composite_errs:
        await emit.emit_progress(Step.SHOT_FRAMES, 1.0, message=f"合成完成，{len(composite_errs)}/{len(valid_scenes)} 场景失败")
        raise RuntimeError(
            f"{len(composite_errs)}/{len(valid_scenes)} 场景视频合成失败，首个错误: {composite_errs[0][1]}"
        )

    await emit.emit_progress(Step.SHOT_FRAMES, 1.0, message="所有场景合成完成")
    logger.info("[project=%d] shot_frames step complete", project_id)
