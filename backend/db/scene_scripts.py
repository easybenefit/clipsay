from __future__ import annotations

import aiosqlite

from backend.db._config import DB_PATH
from backend.db.projects import read_story, read_characters


async def load_scene_script_data(project_id: int) -> tuple[str | None, list["CharacterRead"]]:
    async with aiosqlite.connect(DB_PATH) as db:
        story = await read_story(db, project_id)
        characters = await read_characters(db, project_id)
    return story, characters


async def save_scene_scripts(project_id: int, story: str, scenes: list[dict]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM scenes WHERE project_id = ?", (project_id,))
        for si, sc in enumerate(scenes):
            await db.execute(
                "INSERT INTO scenes (project_id, idx, title, content, script) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, si, sc.get("title", ""), sc.get("content", ""),
                 sc.get("script", "")),
            )
        await db.commit()


async def update_scenes(project_id: int, scenes: list[dict]):
    """Update scenes preserving existing shots and composited media."""
    from backend.utils.paths import normalize_local_url

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        existing_frames = {
            (r["scene_idx"], r["shot_idx"]): r for r in await (await db.execute(
                "SELECT s.idx AS scene_idx, sh.idx AS shot_idx, "
                "sh.start_frame_url, sh.end_frame_url, sh.shot_video_url, sh.shot_preview_url "
                "FROM scenes s JOIN shots sh ON sh.scene_id = s.id "
                "WHERE s.project_id = ?", (project_id,))).fetchall()
        }
        await db.execute("DELETE FROM scenes WHERE project_id = ?", (project_id,))
        for si, sc in enumerate(scenes):
            cur = await db.execute(
                "INSERT INTO scenes (project_id, idx, title, content, "
                "environment_desc, script, composited_video, composited_preview) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, si, sc.get("title", ""), sc.get("content", ""),
                 sc.get("environment_desc", ""), sc.get("script", ""),
                 normalize_local_url(sc.get("composited_video", "")),
                 normalize_local_url(sc.get("composited_preview", ""))),
            )
            scid = cur.lastrowid
            shots = sc.get("shots", [])
            for shi, sh in enumerate(shots):
                prev = existing_frames.get((si, shi), {})
                sf_url = normalize_local_url(sh.get("firstFrame", sh.get("first_frame", "")) or prev.get("start_frame_url", ""))
                ef_url = normalize_local_url(sh.get("lastFrame", sh.get("last_frame", "")) or prev.get("end_frame_url", ""))
                sv_url = normalize_local_url(sh.get("video", "") or prev.get("shot_video_url", ""))
                sp_url = normalize_local_url(
                    sh.get("videoPreview", sh.get("video_preview", ""))
                    or prev.get("shot_preview_url", "")
                )
                await db.execute(
                    "INSERT INTO shots (scene_id, idx, is_last, cam_idx, "
                    "variation_type, visual_desc, audio_desc, motion_desc, "
                    "start_frame_url, end_frame_url, shot_video_url, shot_preview_url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (scid, shi, shi == len(shots) - 1, 0,
                     sh.get("variationType", sh.get("variation_type", "medium")),
                     sh.get("visualDescription", sh.get("visual_description", "")),
                     sh.get("voiceDescription", sh.get("voice_description", "")),
                     sh.get("motionDescription", sh.get("motion_description", "")),
                     sf_url, ef_url, sv_url, sp_url))
        await db.commit()
