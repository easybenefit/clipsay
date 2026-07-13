from __future__ import annotations

import asyncio
import traceback

from backend.utils.image import to_filename
from backend.utils.logging import setup_logger
from backend.db._enums import AssetStatus
from backend.core.types import ImageRef, VIEW_FRONT, VIEW_SIDE, VIEW_BACK, PARALLEL_VIEWS, \
    PORTRAIT_STATUS_GENERATING, PORTRAIT_STATUS_GENERATED, PORTRAIT_STATUS_ERROR
from backend.db import (
    get_characters,
    update_character_portrait_url,
    update_character_portrait_status,
)
from backend.pipeline.events import EventEmitter
from backend.utils.paths import PathResolver

_logger = setup_logger("pipeline.portraits")

# TODO ImageRef这里似乎是不需要，因为可以通过project id使用path_resolver拿到path


async def generate_portraits(config: "SessionConfig", emit: EventEmitter) -> None:
    from backend.services.portrait_generator import PortraitGenerator

    characters = await get_characters(config.project_id)
    if not characters:
        raise ValueError("No characters found; run characters step first")

    generator = PortraitGenerator(
        config.image.model, config.image.api_key, config.image.base_url,
        config.project_id,
    )
    aspect_size = config._get_aspect_size()

    await asyncio.gather(
        *[_generate_character_portraits(generator, emit, character,
                                        aspect_size, config) for character in characters],
    )

    _logger.info("[portraits] done: characters=%d", len(characters))


async def _generate_character_portraits(
    generator: "PortraitGenerator",
    emit: EventEmitter,
    character: "CharacterRead",
    aspect_size: str,
    config: "SessionConfig",
) -> None:
    """Render front, side, and back portraits for one character.

    Each view is persisted to the ``portrait_{view}`` column as soon as it
    completes, so a crash mid-step loses at most the in-flight image —
    not the whole set.

    Front is critical: a failure aborts so the runner can retry the step.
    Side/back errors are absorbed per-view; the existing portrait column is
    left untouched so the UI keeps showing what worked.
    """
    identifier = character.identifier
    _logger.info("[portraits] === character start: %s ===", identifier)

    ref = await _generate_view(
        generator, emit, identifier, character, VIEW_FRONT, aspect_size,
        style=config.style, project_id=config.project_id,
    )
    _logger.info("[portraits] %s front done: url=%s",
                 identifier, ref.url if ref.url else "EMPTY")
    if not ref.url:
        raise RuntimeError(
            f"front missing url for {identifier} after render — DB write may have failed",
        )

    # side/back run in parallel; individual failures don't abort the other
    _logger.info("[portraits] %s side/back start (parallel)", identifier)
    tasks = [
        _generate_view(generator, emit, identifier, character, view, aspect_size,
                       ref=ref, project_id=config.project_id)
        for view in PARALLEL_VIEWS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for view, result in zip(PARALLEL_VIEWS, results):
        if isinstance(result, Exception):
            _logger.error(
                "[portraits] %s %s FAILED: %s\n%s",
                identifier, view, result, "".join(traceback.format_exception(
                    type(result), result, result.__traceback__)),
            )
            await update_character_portrait_status(config.project_id, identifier, view, PORTRAIT_STATUS_ERROR)
        else:
            _logger.info("[portraits] %s %s done url=%s",
                         identifier, view,
                         result.url if result and result.url else "EMPTY")
    await emit.project_data_changed()
    _logger.info("[portraits] %s done", identifier)


async def _generate_view(
    generator: "PortraitGenerator",
    emit: EventEmitter,
    identifier: str,
    character: "CharacterRead",
    view: str,
    aspect_size: str,
    style: str = "",
    ref: ImageRef = None,
    project_id: int = 0,
) -> ImageRef:
    """Render one portrait view (front/side/back) for a character.

    Checks the DB cache first.  For side/back, ``front_url`` is
    stored as the image's ``url`` so the UI can load the front image when
    the side/back hasn't been generated yet.
    """
    # ── mark generating ──
    await update_character_portrait_status(project_id, identifier, view, PORTRAIT_STATUS_GENERATING)
    await emit.project_data_changed()

    # ── generate ──
    if view == VIEW_FRONT:
        ref = await generator.generate_front(
            identifier=identifier, appearance=character.appearance,
            attire=character.attire, style=style, size=aspect_size,
        )
    else:
        method = getattr(generator, f"generate_{view}")
        ref = await method(identifier=identifier, ref=ref, style=style, size=aspect_size)

    if not ref.url:
        await update_character_portrait_status(project_id, identifier, view, PORTRAIT_STATUS_ERROR)
        await emit.project_data_changed()
        raise RuntimeError(
            f"{view} portrait for {identifier}: url is empty after generation")

    # ── persist portrait URL to DB ──
    await update_character_portrait_url(project_id, identifier, view, ref.url)
    await update_character_portrait_status(project_id, identifier, view, PORTRAIT_STATUS_GENERATED)

    await emit.project_data_changed()
    return ref
