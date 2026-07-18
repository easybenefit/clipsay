"""Project-level CRUD operations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import aiosqlite

from backend.utils.paths import DATA_ROOT, normalize_local_url
from backend.schemas.models import ModelConfig


# ── portrait_status bit-field helpers ──────────────────────────────────
_PS_SHIFT = {"front": 0, "back": 4, "side": 8}
_PS_MASK = 0xF

def _ps_decode(val: int) -> dict[str, int]:
    return {v: (val >> s) & _PS_MASK for v, s in _PS_SHIFT.items()}

def _ps_update(current: int, view: str, status: int) -> int:
    shift = _PS_SHIFT[view]
    return (current & ~(_PS_MASK << shift)) | (status << shift)


# ── per-step status constants ─────────────────────────────────────────
STEP_STATUS_COLUMNS: dict[str, str] = {
    "story": "story_status",
    "characters": "characters_status",
    "portraits": "portraits_status",
    "scene_scripts": "scene_scripts_status",
    "storyboard": "storyboard_status",
    "shot_frames": "shot_frames_status",
    "composite_video": "composite_video_status",
}

_STEP_STATUS_COL_NAMES = list(STEP_STATUS_COLUMNS.values())


async def read_step_statuses(project_id: int) -> dict[str, int]:
    cols = ", ".join(_STEP_STATUS_COL_NAMES)
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            f"SELECT {cols} FROM projects WHERE id = ?", (project_id,))).fetchone()
        if not row:
            return {}
        step_map = {}
        for step, col in STEP_STATUS_COLUMNS.items():
            step_map[step] = row[col] or 0
        return step_map


async def update_step_db_status(project_id: int, step_name: str, status: int) -> None:
    col = STEP_STATUS_COLUMNS.get(step_name)
    if not col:
        return
    async with _get_connection() as db:
        await db.execute(
            f"UPDATE projects SET {col} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, project_id))
        await db.commit()


def _get_connection():
    from backend.db._config import DB_PATH
    return aiosqlite.connect(DB_PATH)


async def create_project_row(name: str, language: str = "zh") -> dict:
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO projects (name, language) VALUES (?, ?)", (name, language))
        await db.commit()
        pid = cursor.lastrowid
        row = await (await db.execute("SELECT * FROM projects WHERE id = ?", (pid,))).fetchone()
        return dict(row)


async def list_project_rows(limit: int = 50, offset: int = 0) -> list[dict]:
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT * FROM projects ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset))).fetchall()
        return [dict(r) for r in rows]


async def read_full_project(db: aiosqlite.Connection, project_id: int) -> Optional[dict]:
    db.row_factory = aiosqlite.Row
    row = await (await db.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,))).fetchone()
    if not row:
        return None
    project = dict(row)
    project["story"] = row["story_content"] or None
    project["storyTitle"] = row["story_title"] or ""
    project["step_statuses"] = {step: row[col] or 0 for step, col in STEP_STATUS_COLUMNS.items()}
    project["finalVideoStatus"] = project["step_statuses"].get("composite_video", 0)

    # ── characters from attributes table ──
    char_rows = await (await db.execute(
        "SELECT identifier, appearance, attire, idx, front_url, side_url, back_url, portrait_status FROM attributes "
        "WHERE project_id = ? ORDER BY identifier",
        (project_id,))).fetchall()
    from backend.utils.image import to_filename
    from backend.utils.paths import PathResolver
    _resolver = PathResolver()
    _ps = _resolver.project(project_id).portrait
    project["characters"] = [
        {
            "identifier": r["identifier"],
            "appearance": r["appearance"] or "",
            "attire": r["attire"] or "",
            "idx": r["idx"] or 0,
            "front_url": _ps.url(to_filename(r["identifier"], "front")) if r["front_url"] else "",
            "side_url": _ps.url(to_filename(r["identifier"], "side")) if r["side_url"] else "",
            "back_url": _ps.url(to_filename(r["identifier"], "back")) if r["back_url"] else "",
            "portrait_status": _ps_decode(r["portrait_status"] or 0),
        }
        for r in char_rows
    ]

    sc_rows = await (await db.execute(
        "SELECT * FROM scenes WHERE project_id = ? ORDER BY idx",
        (project_id,))).fetchall()
    project["scenes"] = []
    for sc in sc_rows:
        scene = dict(sc)
        scene_scope = PathResolver().project(project_id).scene(scene["idx"])
        scene["compositedVideo"] = scene.get("composited_video", "")
        scene["compositedPreview"] = scene.get("composited_preview", "")
        scene["compositVideoStatus"] = scene.get("composit_video_status", 0)
        if scene["compositedVideo"] and not scene["compositedVideo"].startswith(("/", "http://", "https://")):
            scene["compositedVideo"] = scene_scope.url(
                scene["compositedVideo"])
            scene["compositedPreview"] = scene_scope.url(
                scene["compositedPreview"])
        sh_rows = await (await db.execute(
            "SELECT * FROM shots WHERE scene_id = ? ORDER BY idx",
            (scene["id"],))).fetchall()
        scene["shots"] = []
        for sh in sh_rows:
            sd = dict(sh)
            sf_path = sd.get("start_frame_path", "")
            sf_url = "/local/" + os.path.relpath(sf_path, str(
                DATA_ROOT)) if sf_path and os.path.exists(sf_path) else normalize_local_url(sd.get("start_frame_url", ""))
            ef_path = sd.get("end_frame_path", "")
            ef_url = "/local/" + os.path.relpath(ef_path, str(
                DATA_ROOT)) if ef_path and os.path.exists(ef_path) else normalize_local_url(sd.get("end_frame_url", ""))
            scene["shots"].append({
                "title": sd["visual_desc"][:50] if sd["visual_desc"] else "",
                "visualDescription": sd["visual_desc"],
                "voiceDescription": sd["audio_desc"],
                "motionDescription": sd["motion_desc"],
                "variationType": sd["variation_type"],
                "firstFrame": sf_url,
                "lastFrame": ef_url,
                "video": sd.get("shot_video_url", ""),
                "videoPreview": sd.get("shot_preview_url", ""),
                "startFrameStatus": sd.get("start_frame_status", 0),
                "endFrameStatus": sd.get("end_frame_status", 0),
                "imageStatus": sd.get("image_status_int", 0),
                "videoStatus": sd.get("video_status", "pending"),
                "videoDependency": sd.get("video_dependency", ""),
            })
        project["scenes"].append(scene)
    return project


async def save_full_project(db, project_id: int, data) -> None:
    fields = {}
    for k in ("name", "language", "idea", "style", "size", "size_tier", "resolution", "frame_rate",
              "duration", "chat_model", "chat_api_key", "chat_base_url",
              "image_model", "image_api_key", "image_base_url",
              "video_model", "video_api_key", "video_base_url"):
        v = getattr(data, k, None)
        if v is not None:
            fields[k] = v
    if fields:
        from datetime import datetime
        sets = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
        await db.execute(f"UPDATE projects SET {sets} WHERE id = ?",
                         (*fields.values(), datetime.now().isoformat(timespec="seconds"), project_id))

    sent = data.model_dump(exclude_unset=True)
    if "story" in sent:
        await db.execute("UPDATE projects SET story_content = ? WHERE id = ?",
                         (sent["story"] or "", project_id))

    if "storyTitle" in sent:
        await db.execute("UPDATE projects SET story_title = ? WHERE id = ?",
                         (sent["storyTitle"] or "", project_id))

    if data.characters is not None:
        db.row_factory = __import__("aiosqlite").Row
        existing_chars = {
            r["identifier"]: r for r in await (await db.execute(
                "SELECT identifier, front_url, side_url, back_url, portrait_status FROM attributes "
                "WHERE project_id = ?", (project_id,))).fetchall()
        }
        await db.execute("DELETE FROM attributes WHERE project_id = ?", (project_id,))
        for i, ch in enumerate(data.characters):
            name = ch.identifier or ""
            prev = existing_chars.get(name, {})
            pd = ch.portraits or {}
            front_url = normalize_local_url(pd.get("front", "")) or prev.get("front_url", "")
            side_url = normalize_local_url(pd.get("side", "")) or prev.get("side_url", "")
            back_url = normalize_local_url(pd.get("back", "")) or prev.get("back_url", "")
            portrait_status = prev.get("portrait_status", 0)
            if front_url:
                portrait_status = _ps_update(portrait_status, "front", 2)
            if side_url:
                portrait_status = _ps_update(portrait_status, "side", 2)
            if back_url:
                portrait_status = _ps_update(portrait_status, "back", 2)
            await db.execute(
                "INSERT INTO attributes (project_id, identifier, appearance, attire, idx, "
                "front_url, side_url, back_url, portrait_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, name, ch.appearance or "", ch.attire or "", ch.idx or i,
                 front_url, side_url, back_url, portrait_status))

    if data.scenes is not None:
        db.row_factory = aiosqlite.Row
        existing_frames = {
            (r["scene_idx"], r["shot_idx"]): r for r in await (await db.execute(
                "SELECT s.idx AS scene_idx, sh.idx AS shot_idx, "
                "sh.start_frame_url, sh.end_frame_url, sh.shot_video_url, sh.shot_preview_url "
                "FROM scenes s JOIN shots sh ON sh.scene_id = s.id "
                "WHERE s.project_id = ?", (project_id,))).fetchall()
        }
        await db.execute("DELETE FROM scenes WHERE project_id = ?", (project_id,))
        for si, sc in enumerate(data.scenes):
            cur = await db.execute(
                "INSERT INTO scenes (project_id, idx, title, content, "
                "environment_desc, script, composited_video, composited_preview) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, si, sc.title, sc.content, sc.environment_desc,
                 sc.script, normalize_local_url(sc.composited_video), normalize_local_url(sc.composited_preview)))
            scid = cur.lastrowid
            if not sc.shots:
                continue
            for shi, sh in enumerate(sc.shots):
                prev = existing_frames.get((si, shi), {})
                sf_url = normalize_local_url(sh.first_frame or prev.get("start_frame_url", ""))
                ef_url = normalize_local_url(sh.last_frame or prev.get("end_frame_url", ""))
                sv_url = normalize_local_url(sh.video or prev.get("shot_video_url", ""))
                sp_url = normalize_local_url(getattr(sh, 'video_preview', '') or getattr(sh, 'videoPreview', '')
                          or prev.get("shot_preview_url", ""))
                await db.execute(
                    "INSERT INTO shots (scene_id, idx, is_last, cam_idx, "
                    "variation_type, visual_desc, audio_desc, motion_desc, "
                    "start_frame_url, end_frame_url, shot_video_url, shot_preview_url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (scid, shi, shi == len(sc.shots) - 1, 0,
                     sh.variation_type, sh.visual_description, sh.voice_description,
                     sh.motion_description, sf_url, ef_url,
                     sv_url, sp_url))
    await db.commit()


async def duplicate_project_full(db, project_id: int) -> Optional[dict]:
    original = await read_full_project(db, project_id)
    if not original:
        return None
    from backend.db._config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO projects (name, language, idea, style, size, resolution, "
            "frame_rate, duration, chat_model, chat_api_key, chat_base_url, "
            "image_model, image_api_key, image_base_url, "
            "video_model, video_api_key, video_base_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"{original['name']} (副本)", original.get("language", "zh"),
             original.get("idea", ""), original.get("style", ""),
             original.get("size", ""), original.get("resolution", ""),
             original.get("frame_rate", 24), original.get("duration", 10),
             original.get("chat_model", ""),
             original.get("chat_api_key", ""), original.get("chat_base_url", ""),
             original.get("image_model", ""),
             original.get("image_api_key", ""), original.get("image_base_url", ""),
             original.get("video_model", ""),
             original.get("video_api_key", ""), original.get("video_base_url", "")))
        new_id = cur.lastrowid
        if original.get("story"):
            await conn.execute(
                "UPDATE projects SET story_content = ?, story_title = ? WHERE id = ?",
                (original["story"], original.get("storyTitle", ""), new_id))
        for ch in original.get("characters", []):
            name = ch.get("identifier", "")
            await conn.execute(
                "INSERT INTO attributes (project_id, identifier, appearance, attire, idx, portrait_status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (new_id, name, ch.get("appearance", ""), ch.get("attire", ""),
                 ch.get("idx", 0), ch.get("portrait_status", 0)))
        for sc in original.get("scenes", []):
            cur = await conn.execute(
                "INSERT INTO scenes (project_id, idx, title, content, "
                "environment_desc, script, composited_video, composited_preview) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (new_id, sc.get("idx", 0), sc.get("title", ""), sc.get("content", ""),
                 sc.get("environment_desc", ""), sc.get("script", ""),
                 normalize_local_url(sc.get("compositedVideo", "")), normalize_local_url(sc.get("compositedPreview", ""))))
            scid = cur.lastrowid
            for sh in sc.get("shots", []):
                await conn.execute(
                    "INSERT INTO shots (scene_id, idx, is_last, cam_idx, "
                    "variation_type, visual_desc, audio_desc, motion_desc, "
                    "start_frame_url, end_frame_url, shot_video_url, shot_preview_url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (scid, sh.get("idx", 0), sh.get("isLast", False), 0,
                     sh.get("variationType", "medium"), sh.get(
                         "visualDescription", ""),
                     sh.get("voiceDescription", ""), sh.get(
                         "motionDescription", ""),
                     normalize_local_url(sh.get("firstFrame", "")), normalize_local_url(sh.get("lastFrame", "")),
                     normalize_local_url(sh.get("video", "")), normalize_local_url(sh.get("videoPreview", ""))))
        await conn.commit()
    return await read_full_project(db, new_id)


async def update_story_content(project_id: int, content: str, title: str = "", **kwargs) -> None:
    async with _get_connection() as db:
        await db.execute(
            "UPDATE projects SET story_content = ?, story_title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (content, title, project_id))
        await db.commit()


async def get_story(project_id: int) -> str | None:
    async with _get_connection() as db:
        return await read_story(db, project_id)


async def read_story(db, project_id: int) -> str | None:
    db.row_factory = aiosqlite.Row
    row = await (await db.execute(
        "SELECT story_content FROM projects WHERE id = ?", (project_id,))).fetchone()
    return row["story_content"] if row and row["story_content"] else None


async def read_characters(db, project_id: int) -> list:
    from backend.schemas import CharacterRead
    db.row_factory = __import__("aiosqlite").Row
    rows = await (await db.execute(
        "SELECT identifier, appearance, attire, idx, front_url, side_url, back_url, portrait_status FROM attributes "
        "WHERE project_id = ? ORDER BY identifier",
        (project_id,))).fetchall()
    result = []
    for r in rows:
        result.append(CharacterRead(
            identifier=r["identifier"],
            appearance=r["appearance"] or "",
            attire=r["attire"] or "",
            char_idx=r["idx"] or 0,
            front_url=r["front_url"] or "",
            side_url=r["side_url"] or "",
            back_url=r["back_url"] or "",
            portrait_status=_ps_decode(r["portrait_status"] or 0),
        ))
    return result


async def get_characters(project_id: int) -> list:
    async with _get_connection() as db:
        return await read_characters(db, project_id)


async def read_character(project_id: int, identifier: str) -> "CharacterRead | None":
    """Read a single character row by project_id and identifier."""
    from backend.schemas import CharacterRead
    async with _get_connection() as db:
        db.row_factory = __import__("aiosqlite").Row
        row = await (await db.execute(
            "SELECT identifier, appearance, attire, idx, front_url, side_url, back_url, portrait_status FROM attributes "
            "WHERE project_id = ? AND identifier = ?",
            (project_id, identifier))).fetchone()
        if not row:
            return None
        return CharacterRead(
            identifier=row["identifier"],
            appearance=row["appearance"] or "",
            attire=row["attire"] or "",
            char_idx=row["idx"] or 0,
            front_url=row["front_url"] or "",
            side_url=row["side_url"] or "",
            back_url=row["back_url"] or "",
            portrait_status=_ps_decode(row["portrait_status"] or 0),
        )


async def save_characters(project_id: int, characters: list) -> None:
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        existing = {
            r["identifier"]: r for r in await (await db.execute(
                "SELECT identifier, front_url, side_url, back_url, portrait_status FROM attributes "
                "WHERE project_id = ?", (project_id,))).fetchall()
        }

        await db.execute("DELETE FROM attributes WHERE project_id = ?", (project_id,))
        for ch in characters:
            name = ch.identifier or ""
            prev = existing.get(name, {})
            await db.execute(
                "INSERT INTO attributes "
                "(project_id, identifier, appearance, attire, idx, "
                "front_url, side_url, back_url, portrait_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, name, ch.appearance or "", ch.attire or "", ch.idx,
                 prev.get("front_url", ""), prev.get("side_url", ""),
                 prev.get("back_url", ""), prev.get("portrait_status", 0)))
        await db.commit()


async def read_scenes(db, project_id: int) -> list[dict]:
    db.row_factory = aiosqlite.Row
    scenes = []
    for sc in await (await db.execute(
            "SELECT * FROM scenes WHERE project_id = ? ORDER BY idx",
            (project_id,))).fetchall():
        scene = dict(sc)
        sh_rows = await (await db.execute(
            "SELECT * FROM shots WHERE scene_id = ? ORDER BY idx",
            (scene["id"],))).fetchall()
        scene["shots"] = [dict(sh) for sh in sh_rows]
        scenes.append(scene)
    return scenes


async def get_scene_ids(project_id: int) -> list[int]:
    """Return the 0-based scene indices for a project, ordered by idx."""
    async with _get_connection() as db:
        rows = await (await db.execute(
            "SELECT idx FROM scenes WHERE project_id = ? ORDER BY idx",
            (project_id,))).fetchall()
        return [r[0] for r in rows]


async def increment_project_clicks(project_id: int) -> None:
    async with _get_connection() as db:
        await db.execute(
            "UPDATE projects SET clicks = clicks + 1 WHERE id = ? AND final_video != ''",
            (project_id,))
        await db.commit()


async def list_top_completed_projects(limit: int = 4) -> list[dict]:
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT * FROM projects WHERE final_video != '' ORDER BY clicks DESC LIMIT ?",
            (limit,))).fetchall()
        return [dict(r) for r in rows]


async def load_session_config(project_id: int) -> "SessionConfig":
    """Load a SessionConfig from the projects table."""
    from backend.core.types import SessionConfig
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )).fetchone()
        if not row:
            raise ValueError(f"Project {project_id} not found")
        return SessionConfig(
            project_id=project_id,
            idea=row["idea"] or "",
            style=row["style"] or "realistic",
            size=row["size"] or "16:9",
            size_tier=row["size_tier"] or "1K",
            resolution=row["resolution"] or "720p",
            duration=row["duration"] or 10,
            frame_rate=row["frame_rate"] or 24,
            language=row["language"] or "zh",
            chat=ModelConfig(
                model=row["chat_model"] or "",
                api_key=row["chat_api_key"] or "",
                base_url=row["chat_base_url"] or "",
            ),
            image=ModelConfig(
                model=row["image_model"] or "",
                api_key=row["image_api_key"] or "",
                base_url=row["image_base_url"] or "",
            ),
            video=ModelConfig(
                model=row["video_model"] or "",
                api_key=row["video_api_key"] or "",
                base_url=row["video_base_url"] or "",
            ),
        )


async def update_character_portrait_url(project_id: int, identifier: str, view: str, url: str) -> None:
    """Update a portrait URL column (front_url / side_url / back_url) for a character."""
    col = f"{view}_url"
    async with _get_connection() as db:
        await db.execute(
            f"UPDATE attributes SET {col} = ? WHERE project_id = ? AND identifier = ?",
            (url, project_id, identifier),
        )
        await db.commit()


async def update_character_portrait_status(project_id: int, identifier: str, view: str, status: int) -> None:
    """Update one view's portrait_status bit-field for a character, in-place."""
    shift = _PS_SHIFT[view]
    sql = (
        "UPDATE attributes SET portrait_status = "
        "(portrait_status & ?) | ? "
        "WHERE project_id = ? AND identifier = ?"
    )
    mask = ~(_PS_MASK << shift) & 0xFFFFFFFF
    value = status << shift
    async with _get_connection() as db:
        await db.execute(sql, (mask, value, project_id, identifier))
        await db.commit()


async def read_character_portrait_status(project_id: int, identifier: str) -> dict[str, int]:
    """Read a character's portrait_status bit-field, decoded per view."""
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT portrait_status FROM attributes WHERE project_id = ? AND identifier = ?",
            (project_id, identifier))).fetchone()
        if not row:
            return {"front": 0, "side": 0, "back": 0}
        return _ps_decode(row["portrait_status"] or 0)


async def read_character_portrait_urls(project_id: int, identifier: str) -> dict[str, str]:
    """Read a character's portrait URLs (front_url, side_url, back_url) from the DB."""
    async with _get_connection() as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT front_url, side_url, back_url FROM attributes WHERE project_id = ? AND identifier = ?",
            (project_id, identifier))).fetchone()
        if not row:
            return {"front_url": "", "side_url": "", "back_url": ""}
        return {
            "front_url": row["front_url"] or "",
            "side_url": row["side_url"] or "",
            "back_url": row["back_url"] or "",
        }


async def read_step_data(project_id: int, step: str) -> dict | None:
    """Read only the data relevant to a specific pipeline step.

    Uses read_full_project internally (fast for local SQLite), then returns
    a filtered payload with a ``step`` marker so the frontend knows which
    state slice to replace.
    """
    from backend.db._config import DB_PATH

    async with aiosqlite.connect(DB_PATH) as db:
        project = await read_full_project(db, project_id)
    if not project:
        return None

    result: dict = {
        "step": step,
        "step_statuses": project.get("step_statuses", {}),
    }

    if step == "story":
        result["story"] = project.get("story")
        result["storyTitle"] = project.get("storyTitle", "")

    elif step in ("characters", "portraits"):
        result["characters"] = project.get("characters", [])

    elif step in (
        "scene_scripts",
        "storyboard",
        "shot_frames",
    ):
        result["scenes"] = project.get("scenes", [])

    elif step == "composite_video":
        result["scenes"] = project.get("scenes", [])
        result["final_video"] = project.get("final_video", "")
        result["final_preview"] = project.get("final_preview", "")

    return result


async def update_character_features(project_id: int, identifier: str, appearance: str, attire: str) -> None:
    """Update a character's appearance and attire in the attributes table."""
    async with _get_connection() as db:
        await db.execute(
            "UPDATE attributes SET appearance = ?, attire = ? WHERE project_id = ? AND identifier = ?",
            (appearance, attire, project_id, identifier),
        )
        await db.commit()
