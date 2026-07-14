"""Pipeline state management — stored directly in the projects table."""

from __future__ import annotations

from datetime import datetime

from backend.db._config import DB_PATH


async def init_pipeline_steps(project_id: int):
    from backend.db.projects import STEP_STATUS_COLUMNS, update_step_db_status

    for step_name in STEP_STATUS_COLUMNS:
        await update_step_db_status(project_id, step_name, 0)

    async with __import__("aiosqlite").connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET pipeline_status = 'idle', pipeline_step = '', "
            "pipeline_error = '' WHERE id = ?", (project_id,))
        await db.commit()


async def get_pipeline_status(project_id: int) -> dict:
    async with __import__("aiosqlite").connect(DB_PATH) as db:
        db.row_factory = __import__("aiosqlite").Row
        row = await (await db.execute(
            "SELECT pipeline_status, pipeline_step, pipeline_error "
            "FROM projects WHERE id = ?", (project_id,))).fetchone()
        return dict(row) if row else {}


async def update_pipeline_status(project_id: int, status: str,
                                  step: str = "", error: str = ""):
    async with __import__("aiosqlite").connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET pipeline_status = ?, pipeline_step = ?, "
            "pipeline_error = ?, updated_at = ? WHERE id = ?",
            (status, step, error, datetime.now().isoformat(timespec="seconds"), project_id))
        await db.commit()


async def update_step_status(project_id: int, step_name: str,
                              status: str, error: str = ""):
    async with __import__("aiosqlite").connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET pipeline_step = ?, "
            "pipeline_error = ?, updated_at = ? WHERE id = ?",
            (step_name, error,
             datetime.now().isoformat(timespec="seconds"), project_id))
        await db.commit()


async def reset_downstream_steps(project_id: int, from_step: str):
    from backend.pipeline.config import STEP_NAMES
    from backend.db.projects import update_step_db_status

    start_idx = STEP_NAMES.index(from_step)
    for step_name in STEP_NAMES[start_idx:]:
        await update_step_db_status(project_id, step_name, 0)

    async with __import__("aiosqlite").connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET pipeline_status = 'running', pipeline_step = ?, "
            "pipeline_error = '', updated_at = ? WHERE id = ?",
            (from_step, datetime.now().isoformat(timespec="seconds"), project_id))
        await db.commit()
