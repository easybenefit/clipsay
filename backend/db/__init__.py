from __future__ import annotations

from contextlib import asynccontextmanager

from pathlib import Path

import aiosqlite

from backend.db._schema import TABLES, INDEXES, MIGRATIONS
from backend.db.assets import (
    list_projects_with_final_video,
    list_scenes_with_assets,
    list_shots_with_assets,
    update_project_final_video,
)
from backend.db.pipeline import (
    get_pipeline_status,
    init_pipeline_steps,
    reset_downstream_steps,
    update_pipeline_status,
    update_step_status,
)
from backend.db.projects import (
    create_project_row,
    duplicate_project_full,
    get_characters,
    get_scene_count,
    get_story,
    list_project_rows,
    read_characters,
    read_full_project,
    read_scenes,
    read_story,
    save_characters,
    save_full_project,
    update_character_portrait_url,
    update_story,
)
from backend.db._config import DB_PATH


def _get_connection():
    return aiosqlite.connect(DB_PATH)


def PathResolver_root() -> Path:
    from backend.utils.paths import DATA_ROOT
    return DATA_ROOT


async def init_db():
    async with _get_connection() as db:
        for stmt in TABLES:
            await db.executescript(stmt)
        for stmt in MIGRATIONS:
            try:
                await db.execute(stmt)
            except Exception:
                pass
        for stmt in INDEXES:
            try:
                await db.execute(stmt)
            except Exception:
                pass
        await db.commit()


@asynccontextmanager
async def lifespan(app):
    await init_db()
    from backend.pipeline.conductor import get_conductor
    await get_conductor().restore_from_db()
    yield
