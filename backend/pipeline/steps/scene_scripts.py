from __future__ import annotations

from backend.pipeline.events import EventEmitter
from backend.services.script_writer import generate_scene_scripts
from backend.utils.logging import setup_logger
from backend.db.scene_scripts import save_scene_scripts
from backend.pipeline.config import SessionConfig

_logger = setup_logger("pipeline.scene_scripts")


async def write_scene_scripts(config: SessionConfig, emit: EventEmitter) -> None:
    scenes = await generate_scene_scripts(config.project_id)
    _logger.info(
        "[scene_scripts] project=%d scenes=%d",
        config.project_id, len(scenes),
    )
    await save_scene_scripts(config.project_id, scenes)
