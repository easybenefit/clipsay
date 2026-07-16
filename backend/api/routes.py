from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from langchain_core.messages import SystemMessage, HumanMessage

from backend.schemas import (
    CreateProject, GenerateRequest, StoryRequest, CharacterRequest,
    ScriptRequest, SceneStoryboardRequest, PortraitRequest, ProjectUpdate, RateLimitUpdate, RateLimitDefaults,
)
from backend.clients.llm import LLM
from backend.services.story_writer import StoryWriter
from backend.services.character_generator import CharacterGenerator
from backend.services.script_writer import ScriptWriter
from backend.services.video_compositor import VideoCompositor
from backend.utils.paths import PathResolver, DATA_ROOT, normalize_local_url
from backend.pipeline.runner import PipelineRunner
from backend.pipeline.config import scene_requirement
from backend.db import (
    DB_PATH, create_project_row, list_project_rows,
    read_full_project, read_step_data, save_full_project, duplicate_project_full,
    update_step_db_status, update_story_content,
)
from backend.db.scene_scripts import read_scene_script_data
from backend.db.projects import load_session_config, increment_project_clicks, list_top_completed_projects
from backend.pipeline.conductor._types import StageStatus

logger = logging.getLogger("api.routes")

router = APIRouter()

local_root = Path(
    os.environ.get("CLIPSAY_LOCAL_DIR")
    or DATA_ROOT
)
local_root.mkdir(parents=True, exist_ok=True)


class ProjectNotFoundError(HTTPException):
    def __init__(self, project_id: int):
        super().__init__(status_code=404,
                         detail=f"Project {project_id} not found")


def _resolve_video_path(url_or_path: str) -> str | None:
    if not url_or_path:
        return None
    if url_or_path.startswith("/local/"):
        return str(local_root / url_or_path[len("/local/"):])
    if os.path.isabs(url_or_path):
        return url_or_path
    return None


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/api/generate")
async def generate(body: GenerateRequest):
    try:
        messages = []
        if body.system_prompt:
            messages.append(SystemMessage(content=body.system_prompt))
        messages.append(HumanMessage(content=body.prompt))
        result = await LLM.chat(body.model, messages, body.api_key, body.base_url)
        return {"result": result}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@router.post("/api/story")
async def generate_story(body: StoryRequest):
    try:
        writer = StoryWriter(body.model, body.api_key, body.base_url)
        result = await writer.write_story(body.idea, body.user_requirement or None)
        return {"result": result}
    except Exception as e:
        logger.error("Generate story failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@router.post("/api/projects/{project_id}/regenerate-story")
async def regenerate_project_story(project_id: int):
    """只重新生成故事内容，不重置下游流水线步骤。"""
    await update_step_db_status(project_id, "story", StageStatus.REGENERATING)
    try:
        cfg = await load_session_config(project_id)
        from backend.pipeline.steps.story import write_and_save_story
        result = await write_and_save_story(cfg)
        await update_step_db_status(project_id, "story", StageStatus.COMPLETE)
        return {"result": result}
    except Exception as e:
        logger.error("Regenerate story failed: %s", e, exc_info=True)
        await update_step_db_status(project_id, "story", StageStatus.STALE)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@router.post("/api/extract-characters")
async def extract_characters(body: CharacterRequest):
    try:
        extractor = CharacterGenerator(body.model, body.api_key, body.base_url)
        characters_responses = await extractor.generate(body.script)
        flat = []
        for resp in characters_responses:
            for c in resp.characters:
                flat.append(c)
        return {"characters": flat}
    except Exception as e:
        logger.error("Extract characters failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@router.post("/api/scene-scripts")
async def generate_script(body: ScriptRequest):
    try:
        writer = ScriptWriter(body.model, body.api_key, body.base_url)
        scenes = await writer.write_script(
            story=body.story,
            characters_text=body.characters_text or None,
            user_requirement=body.user_requirement or None,
        )
        return {"text": "", "scenes": scenes}
    except Exception as e:
        logger.error("Generate script failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@router.post("/api/generate-portraits")
async def generate_portraits(body: PortraitRequest):
    if not body.characters or len(body.characters) != 1:
        return JSONResponse(status_code=400, content={"error": "仅支持单张图片生成，characters 数量必须为 1"})
    if body.view not in ("front", "side", "back"):
        return JSONResponse(status_code=400, content={"error": f"不支持的角度: {body.view}"})

    from backend.services.portrait_service import PortraitService, PortraitFrontGeneratingError
    service = PortraitService(body.model, body.api_key, body.base_url, body.project_id)
    logger.info("[portraits] === POST /api/generate-portraits view=%s identifier=%s ===",
                body.view, body.characters[0].identifier)

    try:
        return await service.generate(body.characters[0].identifier, body.view, body.style, body.size)
    except PortraitFrontGeneratingError as e:
        return JSONResponse(status_code=409, content={"error": str(e)})
    except Exception as e:
        logger.error("[portraits] generate FAILED: %s", e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/projects")
async def create_project(body: CreateProject):
    return await create_project_row(body.name, body.language)


@router.get("/api/projects")
async def list_projects():
    return await list_project_rows()


@router.get("/api/projects/top-completed")
async def top_completed_projects():
    return await list_top_completed_projects(4)


@router.get("/api/projects/{project_id}")
async def get_project(project_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        project = await read_full_project(db, project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project


@router.get("/api/projects/{project_id}/step-data")
async def get_step_data(project_id: int, step: str):
    if step == "scene_scripts":
        data = await read_scene_script_data(project_id)
    else:
        data = await read_step_data(project_id, step)
    if data is None:
        raise ProjectNotFoundError(project_id)
    return data


@router.post("/api/projects/{project_id}/scene-scripts/generate")
async def regenerate_scene_scripts(project_id: int):
    from backend.services.scene_script_service import generate_scene_scripts
    from backend.db.scene_scripts import save_scene_scripts
    from backend.pipeline.events import event_bus, EventEmitter

    async with aiosqlite.connect(DB_PATH) as db:
        project = await read_full_project(db, project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

    emitter = EventEmitter(event_bus, project_id)

    try:
        scenes = await generate_scene_scripts(project_id)
    except Exception as e:
        logger.error("Generate scene scripts failed (project=%d): %s", project_id, e)
        await emitter.project_data_changed()
        raise HTTPException(status_code=500, detail=str(e))

    await save_scene_scripts(project_id, scenes)
    await emitter.project_data_changed()
    return {"scenes": scenes}


@router.put("/api/projects/{project_id}/scenes")
async def update_project_scenes(project_id: int, request: Request):
    from backend.db.scene_scripts import update_scenes
    try:
        body = await request.json()
        scenes = body.get("scenes", [])
        await update_scenes(project_id, scenes)
        return {"status": "ok"}
    except Exception as e:
        logger.error("Update scenes failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.put("/api/projects/{project_id}")
async def update_project(project_id: int, body: ProjectUpdate):
    async with aiosqlite.connect(DB_PATH) as db:
        exists = await (await db.execute("SELECT id FROM projects WHERE id = ?", (project_id,))).fetchone()
        if not exists:
            raise ProjectNotFoundError(project_id)
        await save_full_project(db, project_id, body)
        project = await read_full_project(db, project_id)
        return project


@router.put("/api/projects/{project_id}/characters/{identifier}")
async def update_project_character(project_id: int, identifier: str, body: dict):
    """Update a single character's appearance and attire."""
    from backend.db.projects import update_character_features
    await update_character_features(
        project_id, identifier,
        body.get("appearance", ""),
        body.get("attire", ""),
    )
    return {"status": "ok"}


@router.post("/api/projects/{project_id}/duplicate")
async def duplicate_project(project_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        result = await duplicate_project_full(db, project_id)
        if result is None:
            raise ProjectNotFoundError(project_id)
        return result


@router.post("/api/projects/{project_id}/click")
async def click_project(project_id: int):
    await increment_project_clicks(project_id)
    return {"ok": True}


@router.get("/api/pipeline/running")
async def pipeline_running():
    """检查是否有任何工程的管线正在运行。"""
    for pid, runner in list(PipelineRunner._instances.items()):
        if runner.is_running():
            return {"running": True, "project_id": pid}
    return {"running": False}


@router.put("/api/pipeline/rate-limits")
async def update_rate_limits(body: RateLimitUpdate):
    """动态更新指定模型的速率限制，立即生效。"""
    from backend.clients.image import Image
    Image.update_rate_limits(model=body.model, rpm=body.rpm, rpd=body.rpd)
    return {"status": "updated"}


@router.put("/api/pipeline/rate-limits/defaults")
async def update_rate_limit_defaults(body: RateLimitDefaults):
    """批量设置各模型的默认限流值（应用启动时调用一次即可）。"""
    from backend.clients.image import Image
    Image.apply_defaults(body.defaults)
    return {"status": "applied", "models": len(body.defaults)}


@router.post("/api/scenes/{scene_id}/composite-video")
async def composite_scene_video(scene_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        scene = await (await db.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,))).fetchone()
        if not scene:
            raise HTTPException(
                status_code=404, detail=f"Scene {scene_id} not found")
        scr = await (await db.execute(
            "SELECT project_id FROM scripts WHERE id = ?", (scene["script_id"],))).fetchone()
        project_id = scr["project_id"] if scr else None
        scene_idx = scene["idx"]

        sb = await (await db.execute(
            "SELECT id FROM storyboards WHERE scene_id = ?", (scene_id,))).fetchone()
        if not sb:
            raise HTTPException(
                status_code=400, detail="Scene has no storyboard")

        shot_rows = await (await db.execute(
            "SELECT * FROM shots WHERE storyboard_id = ? ORDER BY idx",
            (sb["id"],))).fetchall()

    video_paths = []
    for sh in shot_rows:
        resolved = _resolve_video_path(sh["video_url"])
        if resolved:
            video_paths.append(resolved)

    if not video_paths:
        raise HTTPException(
            status_code=400, detail="No shot videos found for this scene")

    scene_dir = PathResolver().project(project_id).scene(
        scene_idx).path("composite.mp4").parent
    scene_dir.mkdir(parents=True, exist_ok=True)
    scene_compositor = VideoCompositor(str(scene_dir))
    try:
        loop = asyncio.get_event_loop()
        output_path = await loop.run_in_executor(
            None, scene_compositor.compose, video_paths, "composite.mp4"
        )
    except Exception as e:
        logger.error("Composite scene %d video failed: %s", scene_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    composite_video_url = f"/local/proj_{project_id}/scenes/{scene_idx}/composite.mp4"
    try:
        loop = asyncio.get_event_loop()
        preview_path = await loop.run_in_executor(
            None, scene_compositor.extract_first_frame, output_path, "preview.jpg"
        )
        preview_url = f"/local/proj_{project_id}/scenes/{scene_idx}/preview.jpg"
    except Exception as e:
        logger.error("Extract scene %d preview frame failed: %s", scene_id, e)
        preview_url = ""

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE scenes SET composited_video = ?, composited_preview = ? WHERE id = ?",
            (normalize_local_url(composite_video_url), normalize_local_url(preview_url), scene_id))
        await db.commit()

    return {"composited_video": composite_video_url, "composited_preview": preview_url, "scene_id": scene_id}


@router.post("/api/projects/{project_id}/composite-video")
async def composite_project_video(project_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        scr = await (await db.execute(
            "SELECT id FROM scripts WHERE project_id = ?", (project_id,))).fetchone()
        if not scr:
            raise HTTPException(
                status_code=400, detail="Project has no script")

        scene_rows = await (await db.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY idx",
            (scr["id"],))).fetchall()

    scene_video_paths = []
    project_root = Path(PathResolver().project(project_id).path("")).parent
    for i, sc in enumerate(scene_rows):
        scene_composite_path = project_root / \
            "scenes" / str(sc["idx"]) / "composite.mp4"
        if scene_composite_path.exists():
            scene_video_paths.append(str(scene_composite_path))
            continue

        resolved = _resolve_video_path(sc["composited_video"])
        if resolved and os.path.exists(resolved):
            scene_video_paths.append(resolved)
            continue

        shot_video_paths = []
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            sb = await (await db.execute(
                "SELECT id FROM storyboards WHERE scene_id = ?", (sc["id"],))).fetchone()
            if sb:
                shot_rows = await (await db.execute(
                    "SELECT * FROM shots WHERE storyboard_id = ? ORDER BY idx",
                    (sb["id"],))).fetchall()
                for sh in shot_rows:
                    resolved_shot = _resolve_video_path(sh["video_url"])
                    if resolved_shot:
                        shot_video_paths.append(resolved_shot)

        if shot_video_paths:
            scene_dir = project_root / "scenes" / str(sc["idx"])
            scene_dir.mkdir(parents=True, exist_ok=True)
            scene_compositor = VideoCompositor(str(scene_dir))
            loop = asyncio.get_event_loop()
            scene_path = await loop.run_in_executor(
                None, scene_compositor.compose, shot_video_paths, "composite.mp4"
            )
            scene_video = f"/local/proj_{project_id}/scenes/{sc['idx']}/composite.mp4"
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE scenes SET composited_video = ? WHERE id = ?",
                    (normalize_local_url(scene_video), sc["id"]))
                await db.commit()
            scene_video_paths.append(scene_path)

    if not scene_video_paths:
        raise HTTPException(
            status_code=400, detail="No scene videos available to compose")

    project_dir = project_root
    project_dir.mkdir(parents=True, exist_ok=True)
    project_compositor = VideoCompositor(str(project_dir))
    try:
        loop = asyncio.get_event_loop()
        output_path = await loop.run_in_executor(
            None, project_compositor.compose, scene_video_paths, "final.mp4"
        )
    except Exception as e:
        logger.error("Composite project %d video failed: %s", project_id, e)
        return JSONResponse(status_code=500, content={"error": str(e)})

    final_video_url = f"/local/proj_{project_id}/final.mp4"
    final_preview_url = ""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, project_compositor.extract_first_frame, output_path, "final_preview.jpg"
        )
        final_preview_url = f"/local/proj_{project_id}/final_preview.jpg"
    except Exception as e:
        logger.error("Extract final preview frame failed: %s", e)

    actual_duration = 0
    try:
        from moviepy import VideoFileClip
        actual_duration = int(VideoFileClip(output_path).duration)
    except Exception as e:
        logger.error("Read final video duration failed: %s", e)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET final_video = ?, final_preview = ?, duration = ? WHERE id = ?",
            (normalize_local_url(final_video_url), normalize_local_url(final_preview_url), actual_duration, project_id),
        )
        await db.commit()

    return {"final_video": final_video_url, "final_preview": final_preview_url, "project_id": project_id}
