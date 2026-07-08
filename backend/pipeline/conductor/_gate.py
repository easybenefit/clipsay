"""Stage gates: automatic downstream progression when prerequisites complete.

When all upstream stages reach COMPLETE, the gate opens and triggers
the downstream stage automatically.
"""

from __future__ import annotations

from backend.pipeline.conductor._stage_manager import StageManager
from backend.pipeline.conductor._types import (
    SHOT_VIDEO,
    START_FRAME,
    END_FRAME,
    SCENE_PREVIEW_VIDEO,
    PROJECT_COMPOUND_VIDEO,
    StageStatus,
)
from backend.utils.logging import setup_logger

logger = setup_logger("coordinator.gate")


class Gate:
    """Opens downstream stages when their prerequisites are satisfied.

    Three gates form the pipeline's dependency chain:

        start_frame + end_frame  →  shot_video
        all shot_videos          →  scene_preview_video
        all scene_preview_videos →  project_compound_video
    """

    def __init__(self, registry: StageManager) -> None:
        self._registry = registry

    # ── shot-level gate ───────────────────────────────────────────────

    def _check_shot_video(self, project_id: int, scene_idx: int,
                          shot_id: int) -> bool:
        """Return ``True`` when start + end frames are both complete."""
        sf = self._registry.status(project_id, scene_idx, shot_id, START_FRAME)
        if sf < StageStatus.COMPLETE:
            return False
        ef = self._registry.status(project_id, scene_idx, shot_id, END_FRAME)
        return not (StageStatus.PENDING < ef < StageStatus.COMPLETE)

    # ── scene-level gate ──────────────────────────────────────────────

    def _check_scene_video(self, project_id: int, scene_idx: int,
                           shot_count: int) -> bool:
        """Return ``True`` when every shot's video is complete."""
        for shot_id in range(shot_count):
            if not self._registry.is_complete(project_id, scene_idx, shot_id, SHOT_VIDEO):
                return False
        return True

    # ── project-level gate ────────────────────────────────────────────

    def _check_project_video(self, project_id: int, scene_count: int,
                             vault) -> bool:
        """Return ``True`` when every scene's preview video is ready."""
        for scene_idx in range(scene_count):
            event = vault.get_scene_event(project_id, scene_idx)
            if event is None or not event.is_set():
                return False
        return True

    # ── public API: evaluate gates ────────────────────────────────────

    def may_open_shot_video(self, project_id: int, scene_idx: int,
                            shot_id: int) -> bool:
        return self._check_shot_video(project_id, scene_idx, shot_id)

    def may_open_scene_video(self, project_id: int, scene_idx: int,
                             shot_count: int) -> bool:
        return self._check_scene_video(project_id, scene_idx, shot_count)

    def may_open_project_video(self, project_id: int, scene_count: int,
                               vault) -> bool:
        return self._check_project_video(project_id, scene_count, vault)
