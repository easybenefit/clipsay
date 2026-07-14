from __future__ import annotations

from typing import Optional

from backend.core.types import (
    ImageRef,
    PORTRAIT_STATUS_GENERATING,
    PORTRAIT_STATUS_GENERATED,
    PORTRAIT_STATUS_ERROR,
)
from backend.db.projects import (
    read_character_portrait_status,
    update_character_portrait_url,
    update_character_portrait_status,
)
from backend.schemas.character import PortraitCharacter
from backend.services.portrait_generator import PortraitGenerator
from backend.utils.logging import setup_logger

logger = setup_logger("portrait_service")


class PortraitFrontGeneratingError(Exception):
    """正面肖像仍在生成中，此时不能生成侧面或背面肖像。"""


class PortraitService:
    def __init__(self, model: str, api_key: str, base_url: str, project_id: int):
        self._project_id = project_id
        self._generator = PortraitGenerator(model, api_key, base_url, project_id)

    async def generate(
        self,
        character: PortraitCharacter,
        view: str,
        style: str,
        size: Optional[str] = None,
    ) -> dict:
        """为一角色生成指定角度的肖像，落库后返回 {url, source_url}。"""
        identifier = character.identifier

        # 侧面/背面：检查正面是否仍在生成
        if view in ("side", "back"):
            await self._check_front_generating(identifier)

        # 标记生成中
        await update_character_portrait_status(
            self._project_id, identifier, view, PORTRAIT_STATUS_GENERATING)

        # 分发生成
        try:
            ref = await self._do_generate(character, view, style, size)
        except Exception:
            await self._persist_error(identifier, view)
            raise

        if not ref or not ref.url:
            await self._persist_error(identifier, view)
            raise RuntimeError(
                f"{view} portrait for {identifier}: generation returned empty result")

        url = ref.local_url or ref.url
        await self._persist_success(identifier, view, url)
        logger.info("[portraits] %s %s done: %s", identifier, view,
                    url[:60] + "..." if len(url) > 60 else url)

        return {"url": url, "source_url": ref.url}

    async def _check_front_generating(self, identifier: str) -> None:
        statuses = await read_character_portrait_status(
            self._project_id, identifier)
        if statuses.get("front") == PORTRAIT_STATUS_GENERATING:
            raise PortraitFrontGeneratingError(
                "正面肖像图正在生成，请等待完成后再试")

    async def _do_generate(
        self,
        character: PortraitCharacter,
        view: str,
        style: str,
        size: Optional[str] = None,
    ) -> ImageRef:
        if view == "front":
            return await self._generator.generate_front(
                identifier=character.identifier,
                appearance=character.appearance,
                attire=character.attire,
                style=style,
                size=size,
            )

        if not character.front_image:
            raise ValueError(f"生成{view}肖像需要正面肖像图")
        method = getattr(self._generator, f"generate_{view}")
        return await method(
            identifier=character.identifier,
            ref=ImageRef(url=character.front_image),
            style=style,
            size=size,
        )

    async def _persist_success(
        self, identifier: str, view: str, url: str
    ) -> None:
        await update_character_portrait_url(
            self._project_id, identifier, view, url)
        await update_character_portrait_status(
            self._project_id, identifier, view, PORTRAIT_STATUS_GENERATED)

    async def _persist_error(self, identifier: str, view: str) -> None:
        try:
            await update_character_portrait_status(
                self._project_id, identifier, view, PORTRAIT_STATUS_ERROR)
        except Exception:
            pass
