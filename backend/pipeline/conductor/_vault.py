"""Persistent storage for pipeline artifact metadata.

Holds in-memory references to generated outputs (video paths, preview URLs)
per scene and per project, and can restore state from the database on startup.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from backend.pipeline.conductor._types import (
    SCENE_PREVIEW_VIDEO,
    PROJECT_COMPOUND_VIDEO,
    ArtifactRef,
    SceneKey,
    ProjectKey,
    SceneNotRegisteredError,
    ProjectNotRegisteredError,
)
from backend.utils.logging import setup_logger
from backend.schemas.shot_spec import ShotSpec

logger = setup_logger("coordinator.vault")


class ArtifactVault:
    """In-memory store for pipeline artifact metadata.

    Responsibilities:
    - Scene / project registration metadata (sb_id, shot count).
    - Scene / project generated output URLs and paths.
    - Scene / project ``asyncio.Event`` instances for downstream waiters.
    - DB restoration on startup.
    """

    def __init__(self) -> None:
        self._scene_events: Dict[SceneKey, Dict[str, asyncio.Event]] = {}
        self._project_events: Dict[ProjectKey, Dict[str, asyncio.Event]] = {}
        self._scene_payloads: Dict[SceneKey, ArtifactRef] = {}
        self._project_payloads: Dict[ProjectKey, ArtifactRef] = {}
        self._scene_meta: Dict[SceneKey, Dict[str, Any]] = {}
        self._project_meta: Dict[ProjectKey, Dict[str, Any]] = {}

    @staticmethod
    def _normalize_pid(project_id: int | str) -> int:
        if isinstance(project_id, str):
            return int(project_id.replace("proj_", ""))
        return project_id

    # ── registration ──────────────────────────────────────────────────

    def register_scene(
        self,
        project_id: int | str,
        scene_idx: int,
        shot_descriptions: list[ShotSpec],
    ) -> None:
        project_id = self._normalize_pid(project_id)
        skey = (project_id, scene_idx)
        if skey not in self._scene_events:
            self._scene_events[skey] = {SCENE_PREVIEW_VIDEO: asyncio.Event()}
        meta = self._scene_meta.setdefault(skey, {})
        meta["shot_count"] = len(shot_descriptions)

    def register_project(self, project_id: int | str, scene_count: int = 0) -> None:
        project_id = self._normalize_pid(project_id)
        if project_id not in self._project_events:
            self._project_events[project_id] = {
                PROJECT_COMPOUND_VIDEO: asyncio.Event(),
            }
        if scene_count:
            meta = self._project_meta.setdefault(project_id, {})
            meta["scene_count"] = scene_count

    def reset_project(self, project_id: int | str) -> None:
        project_id = self._normalize_pid(project_id)
        for key in list(self._scene_events.keys()):
            if key[0] == project_id:
                del self._scene_events[key]
                self._scene_payloads.pop(key, None)
        for key in list(self._scene_meta.keys()):
            if key[0] == project_id:
                del self._scene_meta[key]
        self._project_events.pop(project_id, None)
        self._project_payloads.pop(project_id, None)

    # ── metadata queries ─────────────────────────────────────────────

    def get_shot_count(self, project_id: int | str, scene_idx: int) -> int:
        project_id = self._normalize_pid(project_id)
        meta = self._scene_meta.get((project_id, scene_idx), {})
        return meta.get("shot_count", 0)

    def get_scene_count(self, project_id: int | str) -> int:
        project_id = self._normalize_pid(project_id)
        meta = self._project_meta.get(project_id, {})
        return meta.get("scene_count", 0)

    # ── scene-level events ────────────────────────────────────────────

    def get_scene_event(self, project_id: int | str, scene_idx: int) -> Optional[asyncio.Event]:
        project_id = self._normalize_pid(project_id)
        skey = (project_id, scene_idx)
        events = self._scene_events.get(skey)
        return events.get(SCENE_PREVIEW_VIDEO) if events else None

    def mark_scene_complete(self, project_id: int | str, scene_idx: int,
                            payload: ArtifactRef) -> None:
        project_id = self._normalize_pid(project_id)
        skey = (project_id, scene_idx)
        self._scene_payloads[skey] = payload
        if skey not in self._scene_events:
            self._scene_events[skey] = {SCENE_PREVIEW_VIDEO: asyncio.Event()}
        self._scene_events[skey][SCENE_PREVIEW_VIDEO].set()

    async def wait_scene(self, project_id: int | str, scene_idx: int,
                         timeout: Optional[float] = None) -> ArtifactRef:
        project_id = self._normalize_pid(project_id)
        skey = (project_id, scene_idx)
        events = self._scene_events.get(skey)
        if events is None:
            raise SceneNotRegisteredError(
                f"Scene ({project_id}, {scene_idx}) not registered"
            )
        coro = events[SCENE_PREVIEW_VIDEO].wait()
        if timeout is not None:
            await asyncio.wait_for(coro, timeout=timeout)
        else:
            await coro
        return self._scene_payloads.get(skey, ArtifactRef())

    def get_scene_payload(self, project_id: int | str, scene_idx: int) -> ArtifactRef:
        project_id = self._normalize_pid(project_id)
        return self._scene_payloads.get((project_id, scene_idx), ArtifactRef())

    # ── project-level events ──────────────────────────────────────────

    def mark_project_complete(self, project_id: int | str,
                              payload: ArtifactRef) -> None:
        project_id = self._normalize_pid(project_id)
        self._project_payloads[project_id] = payload
        if project_id not in self._project_events:
            self._project_events[project_id] = {PROJECT_COMPOUND_VIDEO: asyncio.Event()}
        self._project_events[project_id][PROJECT_COMPOUND_VIDEO].set()

    async def wait_project(self, project_id: int | str,
                           timeout: Optional[float] = None) -> ArtifactRef:
        project_id = self._normalize_pid(project_id)
        events = self._project_events.get(project_id)
        if events is None:
            raise ProjectNotRegisteredError(
                f"Project {project_id} not registered"
            )
        coro = events[PROJECT_COMPOUND_VIDEO].wait()
        if timeout is not None:
            await asyncio.wait_for(coro, timeout=timeout)
        else:
            await coro
        return self._project_payloads.get(project_id, ArtifactRef())

    def get_project_payload(self, project_id: int | str) -> ArtifactRef:
        project_id = self._normalize_pid(project_id)
        return self._project_payloads.get(project_id, ArtifactRef())

    # ── DB restoration ────────────────────────────────────────────────

    def mark_scene_payload_restored(self, project_id: int | str, scene_idx: int,
                                    video_url: str = "",
                                    preview_url: str = "") -> None:
        project_id = self._normalize_pid(project_id)
        skey = (project_id, scene_idx)
        if skey not in self._scene_events:
            self._scene_events[skey] = {SCENE_PREVIEW_VIDEO: asyncio.Event()}
        self._scene_payloads[skey] = ArtifactRef(
            video_path="", preview_url=preview_url, video_url=video_url,
        )
        self._scene_events[skey][SCENE_PREVIEW_VIDEO].set()

    def mark_project_payload_restored(self, project_id: int | str,
                                       video_url: str = "",
                                       preview_url: str = "") -> None:
        project_id = self._normalize_pid(project_id)
        if project_id not in self._project_events:
            self._project_events[project_id] = {PROJECT_COMPOUND_VIDEO: asyncio.Event()}
        self._project_payloads[project_id] = ArtifactRef(
            video_path="", preview_url=preview_url, video_url=video_url,
        )
        self._project_events[project_id][PROJECT_COMPOUND_VIDEO].set()

    async def restore_from_db(self, project_id: int | None = None) -> None:
        """Replay scene/project artifact state from the database.

        When *project_id* is given, only restore that project's artifacts.
        """
        from backend.db import (
            list_scenes_with_assets,
            list_projects_with_final_video,
        )
        import aiosqlite
        from backend.db import DB_PATH

        async with aiosqlite.connect(DB_PATH) as db:
            for row in await list_scenes_with_assets(db):
                pid, sid, video_url, preview_url = row
                if project_id is not None and pid != project_id:
                    continue
                self.mark_scene_payload_restored(pid, sid, video_url, preview_url)

            for row in await list_projects_with_final_video(db):
                pid, video_url, preview_url = row
                if project_id is not None and pid != project_id:
                    continue
                self.mark_project_payload_restored(pid, video_url, preview_url)
