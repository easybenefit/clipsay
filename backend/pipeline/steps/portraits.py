from __future__ import annotations

import asyncio
import traceback
from typing import Optional

from backend.utils.logging import setup_logger
from backend.core.types import ImageRef, VIEW_FRONT, VIEW_SIDE, VIEW_BACK, PARALLEL_VIEWS, \
    PORTRAIT_STATUS_GENERATED
from backend.db import get_characters, update_character_portrait_status
from backend.pipeline.events import EventEmitter

_logger = setup_logger("pipeline.portraits")


async def generate_portraits(config: "SessionConfig", emit: EventEmitter) -> None:
    from backend.services.portrait_service import PortraitService

    characters = await get_characters(config.project_id)
    if not characters:
        raise ValueError("No characters found; run characters step first")

    service = PortraitService(
        config.image.model, config.image.api_key, config.image.base_url,
        config.project_id,
    )
    aspect_size = config._get_aspect_size()

    await asyncio.gather(
        *[_generate_character_portraits(service, emit, character,
                                        aspect_size, config) for character in characters],
    )

    _logger.info("[portraits] done: characters=%d", len(characters))


def _is_generated(character: "CharacterRead", view: str) -> bool:
    ps = character.portrait_status or {}
    return ps.get(view) == PORTRAIT_STATUS_GENERATED and bool(getattr(character, f"{view}_url", ""))


async def _generate_character_portraits(
    service: "PortraitService",
    emit: EventEmitter,
    character: "CharacterRead",
    aspect_size: str,
    config: "SessionConfig",
) -> None:
    identifier = character.identifier
    _logger.info("[portraits] character start: %s .", identifier)

    # ── voiceover-only: mark as generated without API call ──
    if "（画外音）" in identifier:
        _logger.info("[portraits] %s 为画外音角色，跳过肖像生成", identifier)
        for view in (VIEW_FRONT, VIEW_SIDE, VIEW_BACK):
            await update_character_portrait_status(
                config.project_id, identifier, view, PORTRAIT_STATUS_GENERATED)
        await emit.project_data_changed()
        return

    # ── front ──
    if _is_generated(character, VIEW_FRONT):
        _logger.info("[portraits] %s front already generated, using cached", identifier)
        front_ref = ImageRef(identifier=identifier, url=character.front_url)
    else:
        front_ref = await _generate_one(
            service, emit, identifier, character, VIEW_FRONT, aspect_size,
            style=config.style,
        )
        _logger.info("[portraits] %s front done: url=%s",
                     identifier, front_ref.url if front_ref.url else "EMPTY")
        if not front_ref.url:
            raise RuntimeError(f"front missing url for {identifier} after render")

    # ── side / back ──
    tasks = []
    views_to_do = []
    for view in PARALLEL_VIEWS:
        if _is_generated(character, view):
            _logger.info("[portraits] %s %s already generated, skipping", identifier, view)
        else:
            views_to_do.append(view)
            tasks.append(_generate_one(service, emit, identifier, character, view,
                                       aspect_size, front_ref=front_ref))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for view, result in zip(views_to_do, results):
            if isinstance(result, Exception):
                _logger.error(
                    "[portraits] %s %s FAILED: %s\n%s",
                    identifier, view, result, "".join(traceback.format_exception(
                        type(result), result, result.__traceback__)),
                )
            else:
                _logger.info("[portraits] %s %s done url=%s",
                             identifier, view,
                             result.url if result and result.url else "EMPTY")

    await emit.project_data_changed()
    _logger.info("[portraits] %s done", identifier)


async def _generate_one(
    service: "PortraitService",
    emit: EventEmitter,
    identifier: str,
    character: "CharacterRead",
    view: str,
    aspect_size: str,
    style: str = "",
    front_ref: Optional[ImageRef] = None,
) -> ImageRef:
    await emit.project_data_changed()

    ref = await service.generate_view(
        identifier=identifier, view=view, style=style,
        appearance=character.appearance, attire=character.attire,
        front_ref=front_ref, size=aspect_size,
    )

    return ref
