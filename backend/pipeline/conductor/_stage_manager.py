"""Manager of every pipeline stage across all projects / scenes / shots."""

from __future__ import annotations

from typing import Dict

from backend.pipeline.conductor._stage import Stage
from backend.pipeline.conductor._types import (
    END_FRAME,
    SHOT_VIDEO,
    START_FRAME,
    STAGE_DEFAULT_TIMEOUT,
    StageKey,
    StageStatus,
)


class StageManager:
    """Manages all :class:`Stage` instances, keyed by :class:`StageKey`.

    Provides lifecycle transitions (start / complete / stale / reset) and
    queries (get / status / is_complete / wait).
    """

    def __init__(self) -> None:
        self._stages: Dict[StageKey, Stage] = {}

    @staticmethod
    def _normalize_pid(project_id: int | str) -> int:
        if isinstance(project_id, str):
            return int(project_id.replace("proj_", ""))
        return project_id

    # ── internal helpers ──────────────────────────────────────────────

    def get_or_create(self, project_id: int | str, scene_idx: int,
                      shot_id: int, resource: str) -> Stage:
        project_id = self._normalize_pid(project_id)
        key = StageKey(project_id, scene_idx, shot_id, resource)
        if key not in self._stages:
            self._stages[key] = Stage(key)
        return self._stages[key]

    # ── state transitions ─────────────────────────────────────────────

    def start(self, project_id: int | str, scene_idx: int,
              shot_id: int, resource: str) -> None:
        self.get_or_create(project_id, scene_idx, shot_id, resource).start()

    def complete(self, project_id: int | str, scene_idx: int,
                 shot_id: int, resource: str) -> None:
        self.get_or_create(project_id, scene_idx, shot_id, resource).complete()

    def stale(self, project_id: int | str, scene_idx: int,
              shot_id: int, resource: str) -> None:
        self.get_or_create(project_id, scene_idx, shot_id, resource).stale()

    def reset(self, project_id: int | str, scene_idx: int,
              shot_id: int, resource: str) -> None:
        self.get_or_create(project_id, scene_idx, shot_id, resource).reset()

    # ── waiting ───────────────────────────────────────────────────────

    async def wait(self, project_id: int | str, scene_idx: int,
                   shot_id: int, resource: str,
                   timeout: float = STAGE_DEFAULT_TIMEOUT) -> None:
        stage = self.get_or_create(project_id, scene_idx, shot_id, resource)
        if stage.is_complete:
            return
        await stage.wait(timeout=timeout)

    # ── queries ───────────────────────────────────────────────────────

    def is_complete(self, project_id: int | str, scene_idx: int,
                    shot_id: int, resource: str) -> bool:
        return self.get_or_create(project_id, scene_idx, shot_id, resource).is_complete

    def status(self, project_id: int | str, scene_idx: int,
               shot_id: int, resource: str) -> StageStatus:
        return self.get_or_create(project_id, scene_idx, shot_id, resource).status

    # ── bulk operations ───────────────────────────────────────────────

    def reset_project(self, project_id: int | str) -> None:
        project_id = self._normalize_pid(project_id)
        for stage in list(self._stages.values()):
            if stage.key.project_id == project_id:
                stage.reset()

    # ── DB restoration ───────────────────────────────────────────────

    async def restore_from_db(self, project_id: int | None = None) -> None:
        """Mark shot-level stages as COMPLETE for assets found on disk.

        When *project_id* is given, only restore that project's stages.
        """
        from backend.db import list_shots_with_assets
        import aiosqlite
        from backend.db import DB_PATH

        async with aiosqlite.connect(DB_PATH) as db:
            for row in await list_shots_with_assets(db):
                pid, sid, shot_id, has_sf, has_ef, has_vid = row
                if project_id is not None and pid != project_id:
                    continue
                if has_sf:
                    self.complete(pid, sid, shot_id, START_FRAME)
                if has_ef:
                    self.complete(pid, sid, shot_id, END_FRAME)
                if has_vid:
                    self.complete(pid, sid, shot_id, SHOT_VIDEO)
