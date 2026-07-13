from __future__ import annotations

from backend.pipeline.events import EventEmitter
from backend.services.script_writer import ScriptWriter
from backend.utils.logging import setup_logger
from backend.db.scene_scripts import load_scene_script_data, save_scene_scripts
from backend.schemas import CharacterRead
from backend.pipeline.config import SessionConfig, scene_requirement

_logger = setup_logger("pipeline.scene_scripts")


def _build_characters_text(characters: list[CharacterRead]) -> str:
    """Render the character roster as a compact multiline block for the prompt."""
    lines: list[str] = []
    for ch in characters:
        lines.append(f"角色: {ch.identifier}")
        if ch.appearance:
            lines.append(f",  静态特征: {ch.appearance}")
        if ch.attire:
            lines.append(f",  动态特征: {ch.attire}")
    return "\n".join(lines)


async def write_scene_scripts(config: SessionConfig, emit: EventEmitter) -> None:
    """Expand the saved story into per-scene scripts.

    Reads the story and characters from the DB, asks ``ScriptWriter`` to
    split it into scenes, then persists the scenes so the storyboard step
    can pick them up.
    """
    story, characters = await load_scene_script_data(config.project_id)
    if not story:
        raise ValueError("No story found; run story step first")

    writer = ScriptWriter(
        config.chat.model, config.chat.api_key, config.chat.base_url)
    characters_text = _build_characters_text(
        characters) if characters else None
    result = await writer.write_script(
        story=story,
        characters_text=characters_text,
        user_requirement=scene_requirement(config.duration),
    )
    scenes = result or []
    _logger.info(
        "[scene_scripts] project=%d scenes=%d chars_in=%d",
        config.project_id, len(scenes), len(characters),
    )

    await save_scene_scripts(config.project_id, story, scenes)
