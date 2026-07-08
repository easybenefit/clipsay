"""Data-loading helpers for the frame-generation pipeline.

Reads project data from the database and constructs domain objects
(``ShotSpec``, ``CameraNode``, characters) needed by
:class:`FrameGenerator`.
"""

from __future__ import annotations

import json
from typing import List

from backend.db.storyboards import (
    get_cameras_by_project_scene,
    get_shots_by_project_scene,
    load_storyboard_data,
)
from backend.schemas.camera import CameraNode
from backend.schemas.shot_spec import ShotSpec
from backend.utils.logging import setup_logger

logger = setup_logger("db.loaders")


async def load_project_data(
    project_id: int,
) -> Tuple[List[dict], list]:
    """Load all scenes and characters for *project_id*.

    Returns ``(scenes, characters)`` where each scene dict has
    at least ``"id"`` and ``"idx"`` keys.
    """
    scenes, characters = await load_storyboard_data(project_id)
    if not scenes:
        raise ValueError("No scenes found; run scene_scripts step first")
    return scenes, characters


async def load_shot_descriptions(
    project_id: int,
    scene_idx: int,
) -> List[ShotSpec] | None:
    """Read shot descriptions for *scene_idx* in *project_id* from the database.

    Returns a list of :class:`ShotSpec` or ``None`` if the scene
    has no shots yet.
    """
    rows = await get_shots_by_project_scene(project_id, scene_idx)
    if not rows:
        return None
    return [
        ShotSpec(
            idx=r["idx"],
            is_last=bool(r["is_last"]),
            cam_idx=r["cam_idx"],
            visual_desc=r.get("visual_desc", ""),
            variation_type=r.get("variation_type", "medium"),
            variation_reason=r.get("variation_reason", ""),
            sf_dec=r.get("sf_dec", ""),
            sf_vis_char_idxs=_parse_int_list(r.get("sf_vis_char_idxs")),
            sf_desc=r.get("sf_desc", ""),
            ef_vis_char_idxs=_parse_int_list(r.get("ef_vis_char_idxs")),
            motion_desc=r.get("motion_desc", ""),
            audio_desc=r.get("audio_desc") or None,
        )
        for r in rows
    ]


async def load_camera_tree(project_id: int, scene_idx: int) -> List[CameraNode] | None:
    """Read the camera tree for *scene_idx* in *project_id* from the database.

    Returns a list of :class:`CameraNode` objects, or ``None`` if
    no cameras exist for this scene.
    """
    rows = await get_cameras_by_project_scene(project_id, scene_idx)
    if not rows:
        return None
    return [
        CameraNode(
            idx=r["idx"],
            active_shot_idxs=json.loads(r["active_shot_idxs"]),
            parent_cam_idx=r.get("parent_cam_id"),
            parent_shot_idx=r.get("parent_shot_idx"),
            reason=r.get("reason") or None,
            is_parent_fully_covers_child=(
                bool(r["is_parent_fully_covers_child"])
                if r.get("is_parent_fully_covers_child") is not None
                else None
            ),
            missing_info=r.get("missing_info") or None,
        )
        for r in rows
    ]


# ── private helpers ────────────────────────────────────────────────


def _parse_int_list(value: object) -> List[int]:
    """Parse a value into a list of ints.

    Handles JSON-encoded strings (from DB text columns),
    actual lists (from in-memory objects), and ``None``.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [int(v) for v in value]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []
