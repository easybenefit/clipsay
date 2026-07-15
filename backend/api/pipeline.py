from __future__ import annotations

import asyncio
import json

import aiosqlite
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.db import (
    DB_PATH, get_pipeline_status, update_pipeline_status, read_full_project,
)
from backend.db.projects import load_session_config
from backend.schemas import (
    PipelineStartRequest, RegenerateStepRequest,
    StoryUpdate, ShotFramesUpdate, RateLimitUpdate,
)
from backend.pipeline.events import event_bus, sse_encode
from backend.pipeline.runner import PipelineRunner
from backend.pipeline.config import SessionConfig, STEP_NAMES

router = APIRouter(prefix="/api/projects/{project_id}/pipeline")


async def _get_project_or_404(project_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        project = await read_full_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


# ── SSE events stream ───────────────────────────────────────────────────────


@router.get("/events")
async def pipeline_events(project_id: int):
    q = event_bus.subscribe(project_id)

    async def event_stream():
        try:
            while True:
                event = await q.get()
                yield sse_encode(event)
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(project_id, q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Pipeline control ────────────────────────────────────────────────────────


@router.post("/start")
async def pipeline_start(project_id: int, body: PipelineStartRequest):
    await _get_project_or_404(project_id)
    cfg = await load_session_config(project_id)
    cfg.chat.api_key = body.chat_api_key or cfg.chat.api_key
    cfg.chat.base_url = body.chat_base_url or cfg.chat.base_url
    cfg.image.api_key = body.image_api_key or cfg.image.api_key
    cfg.image.base_url = body.image_base_url or cfg.image.base_url
    cfg.video.api_key = body.video_api_key or cfg.video.api_key
    cfg.video.base_url = body.video_base_url or cfg.video.base_url

    # persist credentials so regenerate-step and restarts can reload them
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET chat_api_key=?, chat_base_url=?, "
            "image_api_key=?, image_base_url=?, "
            "video_api_key=?, video_base_url=? WHERE id=?",
            (cfg.chat.api_key, cfg.chat.base_url,
             cfg.image.api_key, cfg.image.base_url,
             cfg.video.api_key, cfg.video.base_url,
             project_id),
        )
        await db.commit()

    runner = PipelineRunner.get_for_project(project_id)
    await runner.start(cfg, start_step=body.start_step)
    return {"status": "started"}


@router.post("/pause")
async def pipeline_pause(project_id: int):
    runner = PipelineRunner.get_for_project(project_id)
    await runner.pause()
    return {"status": "paused"}


@router.post("/resume")
async def pipeline_resume(project_id: int):
    runner = PipelineRunner.get_for_project(project_id)
    await runner.resume()
    return {"status": "resumed"}


@router.post("/cancel")
async def pipeline_cancel(project_id: int):
    runner = PipelineRunner.get_for_project(project_id)
    await runner.cancel()
    return {"status": "cancelled"}


@router.post("/regenerate-step")
async def pipeline_regenerate_step(project_id: int, body: RegenerateStepRequest):
    if body.step not in STEP_NAMES:
        raise HTTPException(status_code=400, detail=f"Invalid step: {body.step}")
    await _get_project_or_404(project_id)
    cfg = await load_session_config(project_id)
    cfg.chat.api_key = body.chat_api_key or cfg.chat.api_key
    cfg.chat.base_url = body.chat_base_url or cfg.chat.base_url
    cfg.image.api_key = body.image_api_key or cfg.image.api_key
    cfg.image.base_url = body.image_base_url or cfg.image.base_url
    cfg.video.api_key = body.video_api_key or cfg.video.api_key
    cfg.video.base_url = body.video_base_url or cfg.video.base_url
    runner = PipelineRunner.get_for_project(project_id)
    await runner.regenerate_step(body.step, cfg)
    return {"status": "regenerating", "step": body.step}


@router.put("/rate-limits")
async def pipeline_update_rate_limits(project_id: int, body: RateLimitUpdate):
    from backend.clients.image import Image
    Image.update_rate_limits(model=body.model, rpm=body.rpm, rpd=body.rpd)
    return {"status": "updated"}


@router.get("/status")
async def pipeline_status(project_id: int):
    await _get_project_or_404(project_id)
    runner = PipelineRunner.get_for_project(project_id)
    status = await runner.get_status()
    status["is_running"] = runner.is_running()
    # Fix stale 'running' status: if DB says running but no actual runner task,
    # the previous pipeline was interrupted (process crash/restart).
    # Reset to 'paused' so the UI shows "继续" instead of stuck "正在创作".
    if status.get("pipeline_status") == "running" and not status["is_running"]:
        await update_pipeline_status(project_id, "paused")
        status["pipeline_status"] = "paused"
    return status


# ── Step data editors ───────────────────────────────────────────────────────


@router.put("/step/story")
async def update_pipeline_story(project_id: int, body: StoryUpdate):
    await _get_project_or_404(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO stories (project_id, content) VALUES (?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET content = excluded.content",
            (project_id, body.content),
        )
        await db.commit()
    return {"status": "updated"}


@router.put("/step/shot-frames")
async def update_pipeline_shot_frames(project_id: int, body: ShotFramesUpdate):
    await _get_project_or_404(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        scr = await (await db.execute(
            "SELECT id FROM scripts WHERE project_id = ?", (project_id,)
        )).fetchone()
        if not scr:
            raise HTTPException(status_code=400, detail="No script found")
        for update in body.shots:
            shot_idx = update.get("idx")
            storyboard_id = update.get("storyboard_id")
            if not storyboard_id:
                sc_idx = update.get("scene_idx", 0)
                scenes = await (await db.execute(
                    "SELECT id FROM scenes WHERE script_id = ? ORDER BY idx "
                    "LIMIT 1 OFFSET ?", (scr["id"], sc_idx),
                )).fetchall()
                if scenes:
                    sb = await (await db.execute(
                        "SELECT id FROM storyboards WHERE scene_id = ?",
                        (scenes[0]["id"],),
                    )).fetchone()
                    if sb:
                        storyboard_id = sb["id"]
            if storyboard_id and shot_idx is not None:
                for field in ("visual_desc", "sf_dec", "sf_desc", "audio_desc", "motion_desc"):
                    if field in update:
                        await db.execute(
                            f"UPDATE shots SET {field} = ? WHERE storyboard_id = ? AND idx = ?",
                            (update[field], storyboard_id, shot_idx),
                        )
        await db.commit()
    return {"status": "updated"}
