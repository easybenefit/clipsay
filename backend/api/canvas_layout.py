"""Canvas layout persistence — React Flow node/edge/viewport positions."""

from __future__ import annotations

import json

import aiosqlite
from fastapi import APIRouter, HTTPException

from backend.db import DB_PATH

router = APIRouter()


@router.get("/api/projects/{project_id}/canvas-layout")
async def get_canvas_layout(project_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT layout_json FROM canvas_layouts WHERE project_id = ?",
            (project_id,),
        )).fetchone()
    if not row:
        return {"nodes": [], "edges": [], "viewport": None}
    return json.loads(row[0])


@router.put("/api/projects/{project_id}/canvas-layout")
async def save_canvas_layout(project_id: int, data: dict):
    layout_json = json.dumps(data, ensure_ascii=False)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO canvas_layouts (project_id, layout_json, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(project_id) DO UPDATE SET
                   layout_json = excluded.layout_json,
                   updated_at = datetime('now')""",
            (project_id, layout_json),
        )
        await db.commit()
    return {"ok": True}
