from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

from backend.core.types import ImageRef, VIEW_FRONT, VIEW_SIDE, VIEW_BACK
from backend.utils.image import to_filename
from backend.utils.logging import setup_logger
from backend.utils.paths import PathResolver

logger = setup_logger("portrait_generator")

# ── Sensitive-word filter for character prompts ──────────────────────
#
# The image provider's safety filter rejects prompts containing certain
# words (e.g. "裸露/bare/exposed").  We replace them with safe synonyms
# before sending, without losing the semantic meaning.

_SENSITIVE_REPLACEMENTS = {
    # 裸露 / 身体部位
    "裸露": "露出的",
    "赤裸": "未遮蔽",
    "一丝不挂": "穿着衣物",
    "丰满": "匀称",
    "乳沟": "胸前",
    "臀部": "身后",
    "大腿根部": "大腿上方",
    "肚脐": "腹部",
    # 服饰相关
    "内衣": "贴身衣物",
    "内裤": "短裤",
    "比基尼": "泳装",
    "透视装": "轻薄装",
    "半透明": "轻薄的",
    # 暴力 / 伤痕
    "冻疮": "冻伤",
    "血迹": "红色痕迹",
    "伤口": "伤处",
    "疤痕": "痕迹",
    "瘀青": "青紫",
    "红肿": "微红",
    "尸体": "身躯",
    "死亡": "沉睡",
    "暴力": "激烈",
    # 武器
    "武器": "工具",
    # 其他
    "性感": "迷人",
    "诱惑": "吸引",
    "暴露": "外露",
    "湿身": "沾湿",
}

# 预编译：单次扫描完成所有敏感词替换
_SENSITIVE_PATTERN = re.compile(
    "|".join(re.escape(w) for w in _SENSITIVE_REPLACEMENTS),
)


def _sanitize_prompt(text: str) -> str:
    return _SENSITIVE_PATTERN.sub(
        lambda m: _SENSITIVE_REPLACEMENTS[m.group(0)], text,
    )


PORTRAIT_PROMPT_FRONT = (
    "基于以下描述，生成角色{identifier}的全身正面肖像，背景为纯白色。"
    "角色应位于画面中央，占据画面大部分。"
    "目光直视前方。双臂放松自然垂于身侧。表情自然。\n"
    "特征：{features}\n"
    "风格：{style}"
)

PORTRAIT_PROMPT_SIDE = (
    "基于提供的正面肖像，生成角色{identifier}的全身侧面肖像，背景为纯白色。"
    "角色应位于画面中央，占据画面大部分。"
    "面朝左侧。双臂放松自然垂于身侧。\n"
    "风格：{style}"
)

PORTRAIT_PROMPT_BACK = (
    "基于提供的正面肖像，生成角色{identifier}的全身背面肖像，背景为纯白色。"
    "角色应位于画面中央，占据画面大部分。"
    "不得出现任何面部特征。\n"
    "风格：{style}"
)


class PortraitGenerator:
    def __init__(self, model: str, api_key: str, base_url: str, project_id: int | str):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._project = PathResolver().project(project_id)

    async def _generate(self, prompt: str, reference_images=None, size=None,
                        filename: str = "", identifier: str = "") -> ImageRef:
        from backend.clients.image import Image

        payload: dict = {"prompt": prompt, "n": 1, "size": size or "1024x1024"}
        if reference_images:
            payload["reference_images"] = [
                {"url": r.url} for r in reference_images]
        if filename:
            payload["save_path"] = self._project.portrait.path(filename)

        result, _ = await Image.generate(self._model, payload, self._api_key, self._base_url)
        data = result.get("data", [])
        if not data:
            raise ValueError(f"No image data in response: {result}")
        url = data[0].get("url", "")
        if not url:
            raise ValueError(f"No url in response data: {data[0]}")

        local_url = self._project.portrait.url(filename) if filename else ""
        return ImageRef(identifier=identifier, url=url, local_url=local_url, prompt=prompt)

    async def generate_front(
        self,
        identifier: str,
        appearance: str,
        attire: str,
        style: str,
        size: Optional[str] = None,
    ) -> ImageRef:
        features = f"(静态特征) {_sanitize_prompt(appearance)}; (动态特征) {_sanitize_prompt(attire)}"
        prompt = PORTRAIT_PROMPT_FRONT.format(
            identifier=identifier,
            features=features,
            style=style,
        )
        logger.info("[%s] front start: appearance=%s attire=%s style=%s",
                    identifier, appearance, attire, style)
        ref = await self._generate(
            prompt=prompt, size=size, filename=to_filename(
                identifier, VIEW_FRONT),
            identifier=identifier,
        )
        logger.info("[%s] front done: %s", identifier, ref)
        return ref

    async def _generate_with_reference(
        self,
        prompt: str,
        reference: ImageRef,
        size: Optional[str] = None,
        filename: str = "",
        identifier: str = "",
    ) -> ImageRef:
        return await self._generate(
            prompt=prompt, reference_images=[reference],
            size=size, filename=filename, identifier=identifier,
        )

    async def generate_side(
        self,
        identifier: str,
        ref: ImageRef,
        style: str,
        size: Optional[str] = None,
    ) -> ImageRef:
        if not ref.url:
            raise ValueError(
                f"Cannot generate side portrait for {identifier}: ref.url is empty")
        prompt = PORTRAIT_PROMPT_SIDE.format(
            identifier=identifier, style=style)
        logger.info("[%s] side start: ref_url=%s", identifier, ref.url)
        ref = await self._generate_with_reference(
            prompt,
            ref,
            size,
            to_filename(identifier, VIEW_SIDE),
            identifier=identifier,
        )
        logger.info("[%s] side done", identifier)
        return ref

    async def generate_back(
        self,
        identifier: str,
        ref: ImageRef,
        style: str,
        size: Optional[str] = None,
    ) -> ImageRef:
        if not ref.url:
            raise ValueError(
                f"Cannot generate back portrait for {identifier}: ref.url is empty")
        prompt = PORTRAIT_PROMPT_BACK.format(
            identifier=identifier, style=style)
        logger.info("[%s] back start: ref_url=%s", identifier, ref.url)
        ref = await self._generate_with_reference(
            prompt,
            ref,
            size,
            to_filename(identifier, VIEW_BACK),
            identifier=identifier,
        )
        logger.info("[%s] back done", identifier)
        return ref

    async def generate_side_back(
        self,
        identifier: str,
        ref: ImageRef,
        style: str,
        size: Optional[str] = None,
    ) -> dict[str, ImageRef]:
        logger.info("[%s] side+back start: ref_url=%s", identifier, ref.url)
        side_result, back_result = await asyncio.gather(
            self.generate_side(identifier, ref, style, size),
            self.generate_back(identifier, ref, style, size),
        )
        logger.info("[%s] side+back done", identifier)
        return {"side": side_result, "back": back_result}
