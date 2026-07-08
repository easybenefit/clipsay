"""Facade that combines the pipeline coordination components."""

from __future__ import annotations

from typing import Any, List, Optional

from backend.pipeline.conductor._bus import EventBus
from backend.pipeline.conductor._gate import Gate
from backend.pipeline.conductor._stage_manager import StageManager
from backend.pipeline.conductor._types import (
    START_FRAME,
    END_FRAME,
    SHOT_VIDEO,
    SCENE_VIDEO,
    FINAL_VIDEO,
    StageStatus,
    ArtifactRef,
)
from backend.pipeline.conductor._vault import ArtifactVault
from backend.utils.logging import setup_logger
from backend.schemas.shot_spec import ShotSpec

logger = setup_logger("conductor")


class PipelineConductor:
    """Coordination hub for the multi-level video pipeline.

    Public sub-modules (pipeline code can use these directly):

    * ``stages`` — shot-level lifecycle (start / complete / wait / stale).
    * ``vault`` — scene/project artifact metadata.
    * ``bus`` — pub/sub for external listeners (e.g. SSE).
    * ``gate`` — automatic downstream triggering.

    ``change_stage()`` combines state transition + event emission + gate
    check into a single atomic operation.
    """

    _instance: Optional[PipelineConductor] = None

    # ── singleton ─────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> PipelineConductor:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, instance: PipelineConductor) -> None:
        cls._instance = instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── construction ──────────────────────────────────────────────────

    def __init__(self) -> None:
        self.stages = StageManager()
        self.vault = ArtifactVault()
        self.bus = EventBus()
        self.gate = Gate(self.stages)

    # ── lifecycle ─────────────────────────────────────────────────────

    def register_scene(
        self,
        project_id: int | str,
        scene_idx: int,
        shot_descriptions: List[ShotSpec],
    ) -> None:
        self.vault.register_scene(project_id, scene_idx, shot_descriptions)

    def register_project(self, project_id: int | str, scene_count: int = 0) -> None:
        self.vault.register_project(project_id, scene_count)

    def reset_project(self, project_id: int | str) -> None:
        self.stages.reset_project(project_id)
        self.vault.reset_project(project_id)

    # ── listener (pub/sub) ────────────────────────────────────────────

    def on(self, resource: str, handler) -> None:
        self.bus.on(resource, handler)

    def off(self, resource: str, handler) -> None:
        self.bus.off(resource, handler)

    # ── shot-level stage transition (replaces 9 boilerplate methods) ──

    async def change_stage(
        self,
        project_id: int | str,
        scene_idx: int,
        shot_id: int,
        resource: str,
        target: StageStatus,
        **payload: Any,
    ) -> None:
        if target is StageStatus.CREATING:
            self.stages.start(project_id, scene_idx, shot_id, resource)
        else:
            self.stages.complete(project_id, scene_idx, shot_id, resource)

        status = self.stages.status(project_id, scene_idx, shot_id, resource)
        await self.bus.emit(resource, project_id, scene_idx, status,
                            shot_id=shot_id, **payload)

        await self._auto_trigger(project_id, scene_idx, shot_id, resource)

    async def _auto_trigger(self, project_id: int | str, scene_idx: int,
                            shot_id: int, resource: str) -> None:
        if resource in (START_FRAME, END_FRAME):
            if self.gate.may_open_shot_video(project_id, scene_idx, shot_id):
                logger.info("Gate opened: shot_video for shot %d", shot_id)
                await self.change_stage(project_id, scene_idx, shot_id,
                                        SHOT_VIDEO, StageStatus.COMPLETE)

        if resource == SHOT_VIDEO:
            shot_count = self.vault.get_shot_count(project_id, scene_idx)
            if shot_count and self.gate.may_open_scene_video(project_id, scene_idx, shot_count):
                logger.info(
                    "Gate opened: scene_preview_video for scene %d", scene_idx)
                await self.complete_scene_preview_video(project_id, scene_idx)

    # ── scene: preview_video ──────────────────────────────────────────

    async def complete_scene_preview_video(self, project_id: int | str, scene_idx: int,
                                           video_path: str = "", preview_url: str = "",
                                           video_url: str = "") -> None:
        payload = ArtifactRef(video_path=video_path,
                              preview_url=preview_url, video_url=video_url)
        self.vault.mark_scene_complete(project_id, scene_idx, payload)
        await self.bus.emit(SCENE_VIDEO, project_id, scene_idx,
                            StageStatus.COMPLETE,
                            video_path=video_path, preview_url=preview_url,
                            video_url=video_url)

        scene_count = self.vault.get_scene_count(project_id)
        if scene_count and self.gate.may_open_project_video(project_id, scene_count, self.vault):
            logger.info(
                "Gate opened: project_compound_video for project %d", project_id)
            await self.complete_project_compound_video(project_id)

    async def wait_scene_preview_video(self, project_id: int | str, scene_idx: int,
                                       timeout: Optional[float] = None) -> ArtifactRef:
        return await self.vault.wait_scene(project_id, scene_idx, timeout)

    def get_scene_payload(self, project_id: int | str, scene_idx: int) -> ArtifactRef:
        return self.vault.get_scene_payload(project_id, scene_idx)

    # ── project: compound_video ───────────────────────────────────────

    async def complete_project_compound_video(self, project_id: int | str,
                                              video_path: str = "",
                                              preview_url: str = "",
                                              video_url: str = "") -> None:
        payload = ArtifactRef(video_path=video_path,
                              preview_url=preview_url, video_url=video_url)
        self.vault.mark_project_complete(project_id, payload)
        await self.bus.emit(FINAL_VIDEO, project_id, 0,
                            StageStatus.COMPLETE,
                            video_path=video_path, preview_url=preview_url,
                            video_url=video_url)

    async def wait_project_compound_video(self, project_id: int | str,
                                          timeout: Optional[float] = None) -> ArtifactRef:
        return await self.vault.wait_project(project_id, timeout)

    def get_project_payload(self, project_id: int | str) -> ArtifactRef:
        return self.vault.get_project_payload(project_id)

    # ── DB restoration ────────────────────────────────────────────────

    async def restore_from_db(self, project_id: int | None = None) -> None:
        await self.stages.restore_from_db(project_id)
        await self.vault.restore_from_db(project_id)
