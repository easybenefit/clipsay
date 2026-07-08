from __future__ import annotations

from backend.services.story_writer import StoryWriter
from backend.utils.logging import setup_logger
from backend.db import update_story
from backend.pipeline.config import SessionConfig, Step, duration_requirement
from backend.pipeline.events import EventEmitter

_logger = setup_logger("pipeline.story")


async def generate_story(config: SessionConfig, emit: EventEmitter) -> None:
    """Generate the high-level story outline for ``config.project_id``.

    Writes the result to the ``stories`` table so downstream steps
    (characters, scene_scripts, …) can consume it.
    """
    writer = StoryWriter(
        config.chat.model, config.chat.api_key, config.chat.base_url)
    requirement = duration_requirement(config.duration)
    story = await writer.write_story(config.idea, requirement)
    _logger.info(
        "[story] project=%d chars=%d, idea:%s", config.project_id, len(
            story) or "", config.idea)

    await update_story(
        config.project_id, story,
        idea=config.idea, style=config.style, language=config.language,
        duration=config.duration, user_requirement=requirement, model=config.chat.model,
    )
