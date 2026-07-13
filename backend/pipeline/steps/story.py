from __future__ import annotations

from typing import Optional

from backend.services.story_writer import StoryWriter
from backend.utils.logging import setup_logger
from backend.db import update_story_content
from backend.pipeline.config import SessionConfig, scene_requirement
from backend.pipeline.events import EventEmitter

logger = setup_logger("pipeline.story")


async def write_and_save_story(config: SessionConfig) -> str:
    """Core logic: call StoryWriter and persist result."""
    writer = StoryWriter(
        config.chat.model, config.chat.api_key, config.chat.base_url)
    requirement = scene_requirement(config.duration)

    logger.info("[story] start: project=%d idea=%s requirement=%s",
                config.project_id, config.idea, requirement)
    story = await writer.write_story(config.idea, requirement)
    logger.info("[story] done: project=%d, model=%s, story=%s",
                config.project_id, config.chat.model, story or "")

    await update_story_content(
        config.project_id, story,
        idea=config.idea, style=config.style, language=config.language,
        duration=config.duration, user_requirement=requirement, model=config.chat.model,
    )
    return story


async def generate_story(config: SessionConfig, emit: EventEmitter) -> None:
    """Generate the high-level story outline for ``config.project_id``."""
    await write_and_save_story(config)
