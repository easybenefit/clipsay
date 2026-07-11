"""Per-scene storyboard generation with shot decomposition and camera tree construction."""

from __future__ import annotations

import asyncio
from typing import Optional

from backend.utils.logging import setup_logger
from backend.db.storyboards import (
    load_storyboard_data,
    update_storyboard_shots,
    update_storyboard_cameras,
)
from backend.pipeline.config import SessionConfig, Step, duration_requirement
from backend.pipeline.events import EventEmitter
from backend.schemas.camera import CameraNode
from backend.schemas.character import CharacterRead
from backend.schemas.shot_spec import ShotSpec
from backend.services.camera_tree_builder import CameraTreeBuilder
from backend.services.storyboard_generator import StoryboardGenerator

_logger = setup_logger("pipeline.storyboard_generator")

SceneStoryboardResult = tuple[list[ShotSpec], list[CameraNode]]
"""(shot_descriptions, camera_tree) for one scene."""

_MAX_SCENE_RETRIES = 3
"""Per-scene retry count before failing the entire storyboard step."""


# ===================================================================
#  Entry point — generates storyboards for ALL scenes in parallel
# ===================================================================

async def generate_storyboards(
    config: SessionConfig,
    emit: EventEmitter,
    pause_check: Optional[callable] = None,
) -> None:
    """Load all scenes and generate storyboards concurrently.

    Each scene is retried up to ``_MAX_SCENE_RETRIES`` times.  If any
    scene still fails after all retries, the exception propagates to the
    runner so the pipeline pauses.
    """
    scenes, characters = await load_storyboard_data(config.project_id)
    if not scenes:
        raise ValueError("No scenes found; run scene_scripts step first")

    _logger.info("[storyboard] project_id=%d scenes=%d characters=%d",
                 config.project_id, len(scenes), len(characters))

    # Share one artist across all scenes (reuses the same model config).
    artist = StoryboardGenerator(
        model=config.chat.model,
        api_key=config.chat.api_key,
        base_url=config.chat.base_url,
    )

    tasks = [
        generate_scene_storyboard(config, scene, characters, artist, emit)
        for scene in scenes
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    errors = [r for r in results if isinstance(r, Exception)]
    for e in errors:
        _logger.error("场景分镜生成异常: %s", e, exc_info=e)

    if errors:
        raise RuntimeError(
            f"{len(errors)}/{len(scenes)} 场景分镜生成失败（已重试 {_MAX_SCENE_RETRIES} 次），"
            f"首个错误: {errors[0]}"
        )


# ===================================================================
#  Per-scene storyboard generation
# ===================================================================

async def generate_scene_storyboard(
    config: SessionConfig,
    scene: dict,
    characters: list[CharacterRead],
    artist: StoryboardGenerator,
    emit: EventEmitter,
) -> SceneStoryboardResult:
    """Generate storyboard for a single scene, with retries.

    Flow:
        1. ``artist.design_storyboard`` — generate shot briefs from the script.
        2. ``artist.decompose_visual_description`` — expand each brief into
           full shot descriptions (start/end frame, motion, audio).
        3. ``update_storyboard_shots`` — persist to DB.
        4. ``emit.storyboard_scene_ready`` — notify frontend.
        5. ``CameraTreeBuilder.build`` — build camera transition tree.
        6. ``update_storyboard_cameras`` — persist camera tree.

    Returns:
        ``(shot_descriptions, camera_tree)``
    """
    scene_idx: int = scene.get("idx", 0)

    for attempt in range(1, _MAX_SCENE_RETRIES + 1):
        try:
            return await _run_scene_once(
                config, scene, scene_idx, characters, artist, emit)
        except Exception as e:
            _logger.warning(
                "[storyboard] scene=%d attempt=%d/%d failed: %s",
                scene_idx, attempt, _MAX_SCENE_RETRIES, e,
            )
            if attempt < _MAX_SCENE_RETRIES:
                backoff = min(2 ** attempt, 30)
                await asyncio.sleep(backoff)
                continue
            raise


async def _run_scene_once(
    config: SessionConfig,
    scene: dict,
    scene_idx: int,
    characters: list[CharacterRead],
    artist: StoryboardGenerator,
    emit: EventEmitter,
) -> SceneStoryboardResult:
    """Execute one attempt of the scene storyboard pipeline."""
    await emit.emit_progress(
        Step.STORYBOARD, 0,
        message=f"正在生成场景 {scene_idx + 1} 分镜...",
    )

    # ── 1. Shot briefs ────────────────────────────────────────────────
    brief_shots = await artist.design_storyboard(
        script=scene["content"],
        characters=characters,
        user_requirement=_build_requirement(config),
    )

    # ── 2. Decompose each brief into full descriptions ────────────────
    shot_descs = await asyncio.gather(*[
        artist.decompose_visual_description(
            shot_brief_desc=b, characters=characters)
        for b in brief_shots
    ])
    _logger.info("[storyboard] scene=%d shots=%d", scene_idx, len(shot_descs))
    await emit.emit_progress(
        Step.STORYBOARD, 0.5,
        message=f"场景 {scene_idx + 1}: {len(shot_descs)} 个镜头已分解",
    )

    # ── 3. Persist shots ──────────────────────────────────────────────
    await update_storyboard_shots(config.project_id, scene["idx"], shot_descs)

    # ── 4. Notify frontend ────────────────────────────────────────────
    await emit.project_updated()

    # ── 5. Build camera tree ──────────────────────────────────────────
    camera_tree = await CameraTreeBuilder.build(
        shot_descs=shot_descs,
        model=config.chat.model,
        api_key=config.chat.api_key,
        base_url=config.chat.base_url,
    )
    if not camera_tree:
        raise RuntimeError(
            f"Camera tree 为空，场景 {scene_idx + 1} 的分镜生成失败（LLM 连接错误）"
        )
    _logger.info("[storyboard] scene=%d camera_tree=%s",
                 scene_idx, camera_tree)

    # ── 6. Persist camera tree ────────────────────────────────────────
    await update_storyboard_cameras(config.project_id, scene["idx"], camera_tree)

    await emit.emit_progress(
        Step.STORYBOARD, 1.0,
        message=f"场景 {scene_idx + 1} 分镜生成完成",
    )
    return shot_descs, camera_tree


# ===================================================================
#  Helpers
# ===================================================================

def _build_requirement(config: SessionConfig) -> str | None:
    """Combine duration and style constraints into a single requirement string."""
    parts: list[str] = []
    req = duration_requirement(config.duration)
    if req:
        parts.append(req)
    if config.style:
        parts.append(f"Style: {config.style}")
    return "\n".join(parts).strip() or None
