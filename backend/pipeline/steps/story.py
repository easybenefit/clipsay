from __future__ import annotations

from typing import Optional

from backend.services.story_writer import StoryWriter
from backend.utils.logging import setup_logger
from backend.db import update_story_content
from backend.pipeline.config import SessionConfig, scene_requirement
from backend.pipeline.events import EventEmitter

logger = setup_logger("pipeline.story")


async def generate_story_for_project(project_id: int) -> str:
    """Generate and persist story for a project, loading config from DB.

    Only requires project_id — all other params (idea, style, duration,
    model, api_key, base_url, etc.) are read from the database.
    """
    from backend.db.projects import load_session_config
    cfg = await load_session_config(project_id)
    return await _write_and_save_story(cfg)


async def generate_story(config: SessionConfig, emit: EventEmitter) -> None:
    """Generate the high-level story outline for ``config.project_id``."""
    await _write_and_save_story(config)


async def _write_and_save_story(config: SessionConfig) -> str:
    """Core logic: call StoryWriter and persist result."""
    writer = StoryWriter(
        config.chat.model, config.chat.api_key, config.chat.base_url)
    requirement = scene_requirement(config.duration)

    logger.info("[story] start: project=%d idea=%s requirement=%s",
                config.project_id, config.idea, requirement)
    result = await writer.write_story(config.idea, requirement)
    logger.info("[story] done: project=%d, model=%s, story=%s",
                config.project_id, config.chat.model, result.content[:80] if result.content else "")

    await update_story_content(
        config.project_id, result.content, title=result.title,
        idea=config.idea, style=config.style, language=config.language,
        duration=config.duration, user_requirement=requirement, model=config.chat.model,
    )
    return result.content
