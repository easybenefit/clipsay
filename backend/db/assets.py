"""Asset listing queries — used for state restoration on startup."""

from __future__ import annotations

from backend.db._config import DB_PATH


async def list_shots_with_assets(db) -> list[tuple]:
    db.row_factory = __import__("aiosqlite").Row
    rows = await (await db.execute("""
        SELECT p.id, s.idx, sh.idx,
               sh.start_frame_url, sh.start_frame_path,
               sh.end_frame_url, sh.end_frame_path,
               sh.shot_video_url, sh.shot_video_path
        FROM projects p
        JOIN scenes s ON s.project_id = p.id
        JOIN shots sh ON sh.scene_id = s.id
        WHERE sh.start_frame_url != '' OR sh.start_frame_path != ''
           OR sh.end_frame_url != '' OR sh.end_frame_path != ''
           OR sh.shot_video_url != '' OR sh.shot_video_path != ''
    """)).fetchall()
    result = []
    for r in rows:
        result.append((
            r[0], r[1], r[2],
            bool(r[3] or r[4]),
            bool(r[5] or r[6]),
            bool(r[7] or r[8]),
        ))
    return result


async def list_scenes_with_assets(db) -> list[tuple]:
    db.row_factory = __import__("aiosqlite").Row
    rows = await (await db.execute("""
        SELECT p.id, s.idx, s.composited_video, s.composited_preview
        FROM projects p
        JOIN scenes s ON s.project_id = p.id
        WHERE s.composited_video != '' OR s.composited_preview != ''
    """)).fetchall()
    result = []
    for r in rows:
        pid, sidx, vid, prev = r[0], r[1], r[2] or "", r[3] or ""
        # Convert filenames to full /local/ URLs
        vid_url = f"/local/proj_{pid}/scenes/{sidx}/{vid}" if vid and not vid.startswith("/") else vid
        prev_url = f"/local/proj_{pid}/scenes/{sidx}/{prev}" if prev and not prev.startswith("/") else prev
        result.append((pid, sidx, vid_url, prev_url))
    return result


async def list_projects_with_final_video(db) -> list[tuple]:
    db.row_factory = __import__("aiosqlite").Row
    rows = await (await db.execute("""
        SELECT id, final_video, final_preview FROM projects
        WHERE final_video != '' OR final_preview != ''
    """)).fetchall()
    return [(r[0], r[1] or "", r[2] or "") for r in rows]


async def update_project_final_video(project_id: int, video_url: str, preview_url: str):
    async with __import__("aiosqlite").connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET final_video = ?, final_preview = ? WHERE id = ?",
            (video_url, preview_url, project_id))
        await db.commit()
