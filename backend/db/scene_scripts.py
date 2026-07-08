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
