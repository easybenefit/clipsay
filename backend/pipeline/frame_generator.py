from __future__ import annotations

import asyncio
import logging
import os
import shutil
from typing import TYPE_CHECKING, List, Optional

from backend.utils.logging import setup_logger

from backend.pipeline.conductor import (
    END_FRAME,
    START_FRAME,
    StageStatus,
)
from backend.services.image_generator import ImageGenerator
from backend.core.types import ImageRef
from backend.schemas.models import ModelConfig
from backend.db.storyboards import (
    get_shot_by_project_scene,
    update_shot,
)

if TYPE_CHECKING:
    from backend.schemas.character import CharacterRead
    from backend.schemas.shot_spec import ShotSpec
    from backend.schemas.camera import CameraNode
    from backend.pipeline.conductor import PipelineConductor
    from backend.pipeline.events import EventEmitter
    from backend.utils.paths import SceneScope

logger = setup_logger("frame_generator")


class FrameGenerator:
    def __init__(
        self,
        image_config: ModelConfig,
        chat_config: ModelConfig,
        size: str = "1024x576",
        vision_config: ModelConfig | None = None,
        emit: Optional["EventEmitter"] = None,
    ):
        self._image_generator = ImageGenerator(
            image_config=image_config,
            chat_config=chat_config,
            size=size,
            vision_config=vision_config,
        )
        self._emit = emit

    # ── helpers ────────────────────────────────────────────────────

    def _frame_type(self, resource: str) -> str:
        """Strip file extension from a resource name to get the frame type.
        ``"start_frame.png"`` → ``"start_frame"``.
        """
        return os.path.splitext(resource)[0]

    # ------------------------------------------------------------------
    # Public generation methods
    # ------------------------------------------------------------------

    async def _try_use_existing(
        self,
        scene: "SceneScope",
        shot_idx: int,
        resource: str,
        conductor: "PipelineConductor",
        log_tag: str = "",
    ) -> bool:
        """If the frame file exists on disk, fire the complete event
        and return ``True``.  Returns ``False`` when generation is needed.
        """
        frame_path = scene.shot(shot_idx).path(resource)
        if not os.path.exists(frame_path):
            return False

        log_prefix = f"[{log_tag}] " if log_tag else ""
        logger.info("%sshot=%d %s already exists",
                    log_prefix, shot_idx, resource)
        url = scene.shot(shot_idx).url(resource)
        await conductor.change_stage(
            scene.project_id, scene.scene_idx, shot_idx, resource, StageStatus.COMPLETE, url=url,
        )
        if self._emit:
            await self._emit.project_updated()
        return True

    async def _build_ref_image(
        self,
        project_id: int,
        scene_idx: int,
        shot_id: int,
        scene: "SceneScope",
    ) -> Optional[ImageRef]:
        """Query the database for a shot's start frame and return an ``ImageRef``."""
        shot = await get_shot_by_project_scene(project_id, scene_idx, shot_id)
        if not shot:
            return None
        return ImageRef(
            url=shot.get("start_frame_url") or "",
            prompt=shot.get("sf_dec") or "",
        )

    async def generate_first_shot_frame(
        self,
        camera: "CameraNode",
        shot_specs: List["ShotSpec"],
        characters: List["CharacterRead"],
        conductor: "PipelineConductor",
        scene: "SceneScope",
    ) -> None:
        shot_idx = camera.active_shot_idxs[0]
        shot_spec = shot_specs[shot_idx]
        shot_scope = scene.shot(shot_idx)
        scene_idx = scene.scene_idx
        project_id = scene.project_id
        logger.info("[cam=%d shot=%d] generating first shot frame, parent_shot_idx=%s",
                    camera.idx, shot_idx, camera.parent_shot_idx)

        # ── wait for parent, then mark CREATING ──
        if camera.parent_shot_idx is not None:
            logger.info("[cam=%d shot=%d] waiting for parent shot=%d START_FRAME...",
                        camera.idx, shot_idx, camera.parent_shot_idx)
            await conductor.stages.wait(project_id, scene_idx, camera.parent_shot_idx, START_FRAME)
            logger.info("[cam=%d shot=%d] parent shot=%d START_FRAME ready",
                        camera.idx, shot_idx, camera.parent_shot_idx)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self._generate_first_shot_frame(
                    camera, characters, conductor, scene,
                    shot_idx, shot_spec, shot_scope, scene_idx, project_id,
                )
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                delay = 2 ** attempt
                logger.warning("[cam=%d shot=%d] attempt %d/%d failed, retrying in %ds... (%s: %s)",
                               camera.idx, shot_idx, attempt + 1, max_retries, delay,
                               type(e).__name__, e)
                await asyncio.sleep(delay)

    async def _generate_first_shot_frame(
        self,
        camera: "CameraNode",
        characters: List["CharacterRead"],
        conductor: "PipelineConductor",
        scene: "SceneScope",
        shot_idx: int,
        shot_spec: "ShotSpec",
        shot_scope: "SceneScope",
        scene_idx: int,
        project_id: int,
    ) -> None:
        # logger.info("[cam=%d shot=%d] checking for existing START_FRAME",
        #             camera.idx, shot_idx)

        # existing = await self._try_use_existing(
        #     scene, shot_idx, START_FRAME, conductor, log_tag=f"cam={camera.idx}",
        # )
        # if existing:
        #     logger.info("[cam=%d shot=%d] START_FRAME already exists, skipping",
        #                 camera.idx, shot_idx)
        #     return

        logger.info("[cam=%d shot=%d] marking START_FRAME CREATING",
                    camera.idx, shot_idx)

        await update_shot(project_id, scene_idx, shot_idx, start_frame_status=StageStatus.CREATING)
        await conductor.change_stage(project_id, scene_idx, shot_idx, START_FRAME, StageStatus.CREATING)
        if self._emit:
            await self._emit.project_updated()

        # ── build parent composition reference ──
        parent_ref = None
        parent_frame_path = None
        if camera.parent_shot_idx is not None:
            logger.info("[cam=%d shot=%d] loading parent shot=%d data for copy ref",
                        camera.idx, shot_idx, camera.parent_shot_idx)
            parent_shot_spec = await get_shot_by_project_scene(project_id, scene_idx, camera.parent_shot_idx)
            if parent_shot_spec:
                parent_ref = ImageRef(
                    url=parent_shot_spec.get("start_frame_url") or "",
                    prompt=parent_shot_spec.get("sf_dec") or "",
                )
                parent_frame_path = parent_shot_spec.get(
                    "start_frame_path") or ""
                logger.info("[cam=%d shot=%d] parent ref loaded: path=%s",
                            camera.idx, shot_idx, parent_frame_path)

        # ── copy from parent or AI-generate ──
        current_frame_path = shot_scope.path(START_FRAME)
        if camera.parent_cam_idx is not None and camera.missing_info is None:
            if camera.parent_shot_idx is None:
                logger.warning("[cam=%d shot=%d] parent_cam_idx set but parent_shot_idx is None, falling back to AI generation",
                               camera.idx, shot_idx)
                ref = await self._image_generator.generate(
                    shot_idx=shot_idx,
                    frame_type=START_FRAME,
                    frame_description=shot_spec.sf_dec,
                    vis_char_idxs=shot_spec.sf_vis_char_idxs,
                    characters=characters,
                    scene=scene,
                    extra_references=[parent_ref] if parent_ref else None,
                )
            else:
                logger.info("[cam=%d shot=%d] copying parent start_frame from %s to %s",
                            camera.idx, shot_idx, parent_frame_path, current_frame_path)
                parent_shot_scope = scene.shot(camera.parent_shot_idx)
                shutil.copy(parent_shot_scope.path(
                    START_FRAME), current_frame_path)

                ref = ImageRef(url=parent_ref.url if parent_ref else "")
                logger.info(
                    "[cam=%d shot=%d] copied parent start_frame", camera.idx, shot_idx)
        else:
            logger.info("[cam=%d shot=%d] calling AI to generate start_frame (parent_ref=%s, missing_info=%s)",
                        camera.idx, shot_idx,
                        bool(parent_ref), camera.missing_info)
            ref = await self._image_generator.generate(
                shot_idx=shot_idx,
                frame_type=START_FRAME,
                frame_description=shot_spec.sf_dec,
                vis_char_idxs=shot_spec.sf_vis_char_idxs,
                characters=characters,
                scene=scene,
                extra_references=[parent_ref] if parent_ref else None,
            )
            logger.info("[cam=%d shot=%d] start_frame AI generation done, url=%s",
                        camera.idx, shot_idx, ref.url)

        if (not os.path.exists(current_frame_path)
                or os.path.getsize(current_frame_path) == 0):
            logger.error(
                "[cam=%d shot=%d] start_frame file missing after generation: %s "
                "(url=%s)",
                camera.idx, shot_idx, current_frame_path, ref.url,
            )
            raise RuntimeError(
                f"start_frame file missing after generation: {current_frame_path}"
            )

        logger.info(
            "[cam=%d shot=%d] persisting start_frame to DB", camera.idx, shot_idx)
        kwargs = {"start_frame_path": current_frame_path,
                  "start_frame_status": StageStatus.COMPLETE}
        if ref.url:
            kwargs["start_frame_url"] = ref.url
        await update_shot(project_id, scene_idx, shot_idx, **kwargs)
        logger.info("[cam=%d shot=%d] marking START_FRAME COMPLETE",
                    camera.idx, shot_idx)

        await conductor.change_stage(project_id, scene_idx, shot_idx, START_FRAME, StageStatus.COMPLETE, url=ref.url)
        if self._emit:
            await self._emit.project_updated()

    async def generate_start_frame(
        self,
        camera: "CameraNode",
        shot_spec: "ShotSpec",
        characters: List["CharacterRead"],
        conductor: "PipelineConductor",
        scene: "SceneScope",
    ) -> None:
        await self._generate_shot_frame(
            camera=camera, shot_spec=shot_spec,
            characters=characters, conductor=conductor, scene=scene,
            frame_type=START_FRAME,
            desc_attr="sf_dec", vis_char_attr="sf_vis_char_idxs",
            url_attr="start_frame_url", path_attr="start_frame_path",
            status_attr="start_frame_status", resource=START_FRAME,
        )

    async def generate_end_frame(
        self,
        camera: "CameraNode",
        shot_spec: "ShotSpec",
        characters: List["CharacterRead"],
        conductor: "PipelineConductor",
        scene: "SceneScope",
    ) -> None:
        await self._generate_shot_frame(
            camera=camera, shot_spec=shot_spec,
            characters=characters, conductor=conductor, scene=scene,
            frame_type=END_FRAME,
            desc_attr="sf_desc", vis_char_attr="ef_vis_char_idxs",
            url_attr="end_frame_url", path_attr="end_frame_path",
            status_attr="end_frame_status", resource=END_FRAME,
        )

    async def _generate_shot_frame(
        self,
        camera: "CameraNode",
        shot_spec: "ShotSpec",
        characters: List["CharacterRead"],
        conductor: "PipelineConductor",
        scene: "SceneScope",
        *,
        frame_type: str,
        desc_attr: str,
        vis_char_attr: str,
        url_attr: str,
        path_attr: str,
        status_attr: str,
        resource: str,
    ) -> None:
        shot_idx = shot_spec.idx
        logger.info("[cam=%d shot=%d] generating %s",
                    camera.idx, shot_idx, resource)

        # # ── early skip if already exists ──
        # existing = await self._try_use_existing(
        #     scene, shot_idx, resource, conductor,
        # )
        # if existing:
        #     logger.info("[cam=%d shot=%d] %s already exists, skipping",
        #                 camera.idx, shot_idx, resource)
        #     return

        # ── conductor / db setup ──
        logger.info("[cam=%d shot=%d] waiting for first shot=%d START_FRAME (for %s)",
                    camera.idx, shot_idx, camera.active_shot_idxs[0], resource)
        await conductor.stages.wait(scene.project_id, scene.scene_idx, camera.active_shot_idxs[0], START_FRAME)
        logger.info("[cam=%d shot=%d] first shot=%d START_FRAME ready (for %s)",
                    camera.idx, shot_idx, camera.active_shot_idxs[0], resource)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self._generate_one_frame(
                    camera, shot_spec, characters, conductor, scene,
                    shot_idx, frame_type, desc_attr, vis_char_attr,
                    url_attr, path_attr, status_attr, resource,
                )
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                delay = 2 ** attempt
                logger.warning("[cam=%d shot=%d] %s attempt %d/%d failed, retrying in %ds... (%s: %s)",
                               camera.idx, shot_idx, resource, attempt + 1, max_retries, delay,
                               type(e).__name__, e)
                await asyncio.sleep(delay)

    async def _generate_one_frame(
        self,
        camera: "CameraNode",
        shot_spec: "ShotSpec",
        characters: List["CharacterRead"],
        conductor: "PipelineConductor",
        scene: "SceneScope",
        shot_idx: int,
        frame_type: str,
        desc_attr: str,
        vis_char_attr: str,
        url_attr: str,
        path_attr: str,
        status_attr: str,
        resource: str,
    ) -> None:
        logger.info("[cam=%d shot=%d] marking %s CREATING",
                    camera.idx, shot_idx, resource)
        await update_shot(scene.project_id, scene.scene_idx, shot_idx, **{f"{status_attr}": StageStatus.CREATING})
        await conductor.change_stage(scene.project_id, scene.scene_idx, shot_idx, resource, StageStatus.CREATING)
        if self._emit:
            await self._emit.project_updated()

        logger.info("[cam=%d shot=%d] building reference image for %s",
                    camera.idx, shot_idx, resource)
        ref_image = await self._build_ref_image(
            scene.project_id, scene.scene_idx, camera.active_shot_idxs[0], scene,
        )
        logger.info("[cam=%d shot=%d] ref_image=%s for %s",
                    camera.idx, shot_idx,
                    ref_image.url if ref_image else None, resource)

        logger.info("[cam=%d shot=%d] calling AI to generate %s",
                    camera.idx, shot_idx, resource)
        ref = await self._image_generator.generate(
            shot_idx=shot_idx,
            frame_type=frame_type,
            frame_description=getattr(shot_spec, desc_attr),
            vis_char_idxs=getattr(shot_spec, vis_char_attr),
            characters=characters,
            scene=scene,
            extra_references=[ref_image] if ref_image else None,
        )
        logger.info("[cam=%d shot=%d] %s AI generation done, url=%s",
                    camera.idx, shot_idx, resource, ref.url)

        logger.info("[cam=%d shot=%d] persisting %s to DB",
                    camera.idx, shot_idx, resource)
        frame_path = scene.shot(shot_idx).path(resource)
        if not os.path.exists(frame_path) or os.path.getsize(frame_path) == 0:
            logger.error(
                "[cam=%d shot=%d] %s file missing after generation: %s (url=%s)",
                camera.idx, shot_idx, resource, frame_path, ref.url,
            )
            raise RuntimeError(
                f"{resource} file missing after generation: {frame_path}"
            )
        kwargs = {f"{path_attr}": str(frame_path),
                  f"{status_attr}": StageStatus.COMPLETE}
        if ref.url:
            kwargs[url_attr] = ref.url
        await update_shot(scene.project_id, scene.scene_idx, shot_idx, **kwargs)
        logger.info("[cam=%d shot=%d] marking %s COMPLETE",
                    camera.idx, shot_idx, resource)
        await conductor.change_stage(scene.project_id, scene.scene_idx, shot_idx, resource, StageStatus.COMPLETE, url=ref.url)
        if self._emit:
            await self._emit.project_updated()
