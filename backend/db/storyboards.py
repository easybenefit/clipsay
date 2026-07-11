from __future__ import annotations

import json

import aiosqlite


from backend.db._config import DB_PATH
from backend.db.projects import read_scenes, read_characters


def _normalize_pid(project_id: int | str) -> int:
    if isinstance(project_id, str):
        return int(project_id.replace("proj_", ""))
    return project_id


async def load_storyboard_data(project_id: int) -> tuple[list[dict], list["CharacterRead"]]:
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        scenes = await read_scenes(db, project_id)
        characters = await read_characters(db, project_id)
    return scenes, characters


async def _resolve_scene_id(project_id: int | str, scene_idx: int) -> int | None:
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT id FROM scenes WHERE project_id = ? AND idx = ?",
            (project_id, scene_idx),
        )).fetchone()
        return row[0] if row else None


async def update_storyboard_shots(
    project_id: int | str,
    scene_idx: int,
    shot_descriptions: list["ShotSpec"],
) -> None:
    """Insert all shot descriptions for a scene."""
    project_id = _normalize_pid(project_id)
    scene_id = await _resolve_scene_id(project_id, scene_idx)
    if scene_id is None:
        raise ValueError(f"Scene (project={project_id}, idx={scene_idx}) not found")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM shots WHERE scene_id = ?", (scene_id,))
        shot_values = [
            (scene_id, sd.idx, sd.is_last, sd.cam_idx, sd.variation_type,
             sd.visual_desc, sd.audio_desc or "",
             sd.sf_dec, sd.sf_desc, sd.motion_desc,
             json.dumps(sd.sf_vis_char_idxs), json.dumps(sd.ef_vis_char_idxs),
             "pending", "pending", "pending", 0)
            for sd in shot_descriptions
        ]
        await db.executemany(
            "INSERT INTO shots (scene_id, idx, is_last, cam_idx, "
            "variation_type, visual_desc, audio_desc, sf_dec, sf_desc, "
            "motion_desc, sf_vis_char_idxs, ef_vis_char_idxs, "
            "status, image_status, video_status, image_status_int) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            shot_values,
        )
        await db.commit()


async def update_storyboard_cameras(
    project_id: int | str,
    scene_idx: int,
    camera_tree: list["CameraNode"],
) -> None:
    """Insert camera entries for a scene."""
    project_id = _normalize_pid(project_id)
    scene_id = await _resolve_scene_id(project_id, scene_idx)
    if scene_id is None:
        raise ValueError(f"Scene (project={project_id}, idx={scene_idx}) not found")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cameras WHERE scene_id = ?", (scene_id,))
        cam_values = [
            (scene_id, cam.idx, json.dumps(cam.active_shot_idxs),
             cam.parent_cam_idx, cam.parent_shot_idx,
             cam.reason or "",
             int(cam.is_parent_fully_covers_child) if cam.is_parent_fully_covers_child is not None else 0,
             cam.missing_info or "")
            for cam in camera_tree
        ]
        await db.executemany(
            "INSERT INTO cameras (scene_id, idx, active_shot_idxs, "
            "parent_cam_id, parent_shot_idx, reason, "
            "is_parent_fully_covers_child, missing_info) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            cam_values,
        )
        await db.commit()


async def update_shot(
    project_id: int | str, scene_idx: int, shot_idx: int,
    *,
    start_frame_url: str | None = None,
    start_frame_path: str | None = None,
    end_frame_url: str | None = None,
    end_frame_path: str | None = None,
    shot_video_url: str | None = None,
    shot_video_path: str | None = None,
    shot_preview_url: str | None = None,
    source_url: str | None = None,
    start_frame_status: int | None = None,
    end_frame_status: int | None = None,
    image_status: int | None = None,
    video_status: str | None = None,
    video_dependency: str | None = None,
):
    project_id = _normalize_pid(project_id)
    sets: list[str] = []
    vals: list = []

    for col in ("start_frame_url", "start_frame_path",
                "end_frame_url", "end_frame_path",
                "shot_video_url", "shot_video_path",
                "shot_preview_url", "source_url"):
        val = locals()[col]
        if val is not None:
            sets.append(f"{col} = ?")
            vals.append(val)

    for col in ("start_frame_status", "end_frame_status",
                "image_status", "video_status", "video_dependency"):
        val = locals()[col]
        if val is not None:
            sets.append(f"{col} = ?")
            vals.append(val)

    if not sets:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT id FROM scenes WHERE project_id = ? AND idx = ?",
            (project_id, scene_idx),
        )).fetchone()
        scene_id = row[0] if row else None
        if scene_id is None:
            raise ValueError(f"Scene (project={project_id}, idx={scene_idx}) not found")
        vals.extend([scene_id, shot_idx])
        await db.execute(
            f"UPDATE shots SET {', '.join(sets)} WHERE scene_id = ? AND idx = ?",
            vals,
        )
        await db.commit()


async def get_shots_by_project_scene(project_id: int | str, scene_idx: int) -> list[dict]:
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            """SELECT sh.* FROM shots sh
               JOIN scenes sc ON sh.scene_id = sc.id
               WHERE sc.project_id = ? AND sc.idx = ?
               ORDER BY sh.idx""",
            (project_id, scene_idx),
        )).fetchall()
        return [dict(r) for r in rows]


async def get_cameras_by_project_scene(project_id: int | str, scene_idx: int) -> list[dict]:
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            """SELECT ca.* FROM cameras ca
               JOIN scenes sc ON ca.scene_id = sc.id
               WHERE sc.project_id = ? AND sc.idx = ?
               ORDER BY ca.idx""",
            (project_id, scene_idx),
        )).fetchall()
        return [dict(r) for r in rows]


async def get_shot_idxs_by_project_scene(project_id: int | str, scene_idx: int) -> list[int]:
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            """SELECT sh.idx FROM shots sh
               JOIN scenes sc ON sh.scene_id = sc.id
               WHERE sc.project_id = ? AND sc.idx = ?
               ORDER BY sh.idx""",
            (project_id, scene_idx),
        )).fetchall()
        return [r["idx"] for r in rows]


async def get_shot_by_project_scene(
    project_id: int | str, scene_idx: int, shot_idx: int,
) -> dict | None:
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            """SELECT sh.* FROM shots sh
               JOIN scenes sc ON sh.scene_id = sc.id
               WHERE sc.project_id = ? AND sc.idx = ? AND sh.idx = ?""",
            (project_id, scene_idx, shot_idx),
        )).fetchone()
        return dict(row) if row else None


async def update_scene_composite(project_id: int | str, scene_idx: int,
                                  video_filename: str, preview_filename: str):
    """Save composite video filenames to the scenes table."""
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE scenes SET composited_video = ?, composited_preview = ? WHERE project_id = ? AND idx = ?",
            (video_filename, preview_filename, project_id, scene_idx),
        )
        await db.commit()


async def get_shot_frame_url(project_id: int | str, scene_idx: int, shot_idx: int) -> str:
    project_id = _normalize_pid(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            """SELECT sh.start_frame_url FROM shots sh
               JOIN scenes sc ON sh.scene_id = sc.id
               WHERE sc.project_id = ? AND sc.idx = ? AND sh.idx = ?""",
            (project_id, scene_idx, shot_idx),
        )).fetchone()
        return row["start_frame_url"] if row else ""
