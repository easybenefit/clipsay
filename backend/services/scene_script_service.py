from __future__ import annotations

from backend.db.scene_scripts import load_scene_script_data
from backend.db.projects import load_session_config
from backend.pipeline.config import scene_requirement
from backend.services.script_writer import ScriptWriter
from backend.schemas import CharacterRead


def _build_characters_text(characters: list[CharacterRead]) -> str:
    lines: list[str] = []
    for ch in characters:
        lines.append(f"角色: {ch.identifier}")
        if ch.appearance:
            lines.append(f",  静态特征: {ch.appearance}")
        if ch.attire:
            lines.append(f",  动态特征: {ch.attire}")
    return "\n".join(lines)


async def generate_scene_scripts(project_id: int) -> list[dict]:
    config = await load_session_config(project_id)
    story, characters = await load_scene_script_data(project_id)
    if not story:
        raise ValueError("No story found; run story step first")

    writer = ScriptWriter(config.chat.model, config.chat.api_key, config.chat.base_url)
    characters_text = _build_characters_text(characters) if characters else None
    scenes = await writer.write_script(
        story=story,
        characters_text=characters_text,
        user_requirement=scene_requirement(config.duration),
    )
    return scenes or []
