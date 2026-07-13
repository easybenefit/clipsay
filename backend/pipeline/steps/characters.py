from __future__ import annotations

from backend.db import get_story, save_characters
from backend.pipeline.events import EventEmitter
from backend.utils.logging import setup_logger

logger = setup_logger("pipeline.characters")


async def generate_characters(config: "SessionConfig", emit: EventEmitter) -> None:
    from backend.services.character_generator import CharacterGenerator
    from backend.pipeline.config import Step

    await emit.emit_progress(Step.CHARACTERS, 0, message="正在提取角色...")

    story = await get_story(config.project_id)
    if not story:
        raise ValueError("No story found; run story step first")

    await emit.emit_progress(Step.CHARACTERS, 0.3, message="正在生成角色卡片...")
    generator = CharacterGenerator(
        config.chat.model, config.chat.api_key, config.chat.base_url)

    logger.info("[characters] start: project=%d script_len=%d",
                config.project_id, len(story))
    characters = await generator.generate(story)
    logger.info("[characters] done: project=%d count=%d chars=%s",
                config.project_id, len(characters),
                [(c.idx, c.identifier) for c in characters])

    await save_characters(config.project_id, characters)
    await emit.emit_progress(Step.CHARACTERS, 1.0, message=f"已提取 {len(characters)} 个角色")
