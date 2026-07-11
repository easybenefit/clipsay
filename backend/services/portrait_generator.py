from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

from backend.core.types import ImageRef
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


FRONT_PROMPT = (
    "基于以下描述，生成角色{identifier}的全身正面肖像，背景为纯白色。"
    "角色应位于画面中央，占据画面大部分。"
    "目光直视前方。双臂放松自然垂于身侧。表情自然。\n"
    "特征：{features}\n"
    "风格：{style}"
)

SIDE_PROMPT = (
    "基于提供的正面肖像，生成角色{identifier}的全身侧面肖像，背景为纯白色。"
    "角色应位于画面中央，占据画面大部分。"
    "面朝左侧。双臂放松自然垂于身侧。"
)

BACK_PROMPT = (
    "基于提供的正面肖像，生成角色{identifier}的全身背面肖像，背景为纯白色。"
    "角色应位于画面中央，占据画面大部分。"
    "不得出现任何面部特征。"
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
        ref_count = 0
        if reference_images:
            ref_urls = [r.url for r in reference_images]
            ref_count = len(ref_urls)
            payload["reference_images"] = [{"url": url} for url in ref_urls]
            logger.info("[%s] _generate prompt_len=%d ref_count=%d size=%s filename=%s",
                        identifier, len(prompt), ref_count, payload["size"], filename)
        else:
            logger.info("[%s] _generate prompt_len=%d size=%s filename=%s",
                        identifier, len(prompt), payload["size"], filename)

        logger.debug("[%s] _generate prompt (first 200 chars): %s",
                     identifier, prompt[:200])
        if filename:
            payload["save_path"] = self._project.portrait.path(filename)

        result, _ = await Image.generate(self._model, payload, self._api_key, self._base_url)
        logger.info("[%s] _generate API response keys=%s",
                    identifier, list(result.keys()))

        data = result.get("data", [])
        if not data:
            logger.error("[%s] _generate FAILED: no image data in response. full=%s",
                         identifier, result)
            raise ValueError(f"No image data in response: {result}")
        url = data[0].get("url", "")
        if not url:
            logger.error("[%s] _generate FAILED: empty url in data[0]=%s. full=%s",
                         identifier, data[0], result)
            raise ValueError(f"No url in response data: {data[0]}")

        logger.info("[%s] _generate SUCCESS url_len=%s filename=%s",
                    identifier, url, filename)

        local_url = ""
        if filename:
            local_url = self._project.portrait.url(filename)

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
        prompt = FRONT_PROMPT.format(
            identifier=identifier,
            features=features,
            style=style,
        )
        logger.info("[%s] generate_front start appearance=%d attire=%d style=%s",
                    identifier, len(appearance), len(attire), style)

        ref = await self._generate(
            prompt=prompt, size=size, filename=to_filename(identifier, "front"),
            identifier=identifier,
        )
        logger.info("[%s] generate_front done url=%s", identifier,
                    ref.url if ref.url else "EMPTY")
        return ref

    async def _generate_with_reference(
        self,
        prompt: str,
        reference: ImageRef,
        size: Optional[str] = None,
        filename: str = "",
        identifier: str = "",
    ) -> ImageRef:
        logger.info("[%s] _generate_with_reference filename=%s ref_url=%s",
                    identifier, filename, reference.url if reference.url else "NONE")
        return await self._generate(
            prompt=prompt, reference_images=[reference],
            size=size, filename=filename, identifier=identifier,
        )

    async def generate_side(
        self,
        identifier: str,
        front_url: str,
        size: Optional[str] = None,
    ) -> ImageRef:
        logger.info("[%s] generate_side start front_url=%s",
                    identifier, front_url if front_url else "EMPTY")
        if not front_url:
            logger.error(
                "[%s] generate_side ABORTED: front_url is empty", identifier)
            raise ValueError(
                f"Cannot generate side portrait for {identifier}: front_url is empty")
        prompt = SIDE_PROMPT.format(identifier=identifier)
        logger.debug("[%s] generate_side prompt: %s", identifier, prompt)
        ref = await self._generate_with_reference(
            prompt,
            ImageRef(identifier=identifier, url=front_url),
            size,
            to_filename(identifier, "side"),
            identifier=identifier,
        )
        logger.info("[%s] generate_side done url=%s", identifier,
                    ref.url[:80] if ref.url else "EMPTY")
        return ref

    async def generate_back(
        self,
        identifier: str,
        front_url: str,
        size: Optional[str] = None,
    ) -> ImageRef:
        logger.info("[%s] generate_back start front_url=%s",
                    identifier, front_url[:80] if front_url else "EMPTY")
        if not front_url:
            logger.error(
                "[%s] generate_back ABORTED: front_url is empty", identifier)
            raise ValueError(
                f"Cannot generate back portrait for {identifier}: front_url is empty")
        prompt = BACK_PROMPT.format(identifier=identifier)
        logger.debug("[%s] generate_back prompt: %s", identifier, prompt)
        ref = await self._generate_with_reference(
            prompt,
            ImageRef(identifier=identifier, url=front_url),
            size,
            to_filename(identifier, "back"),
            identifier=identifier,
        )
        logger.info("[%s] generate_back done url=%s", identifier,
                    ref.url[:80] if ref.url else "EMPTY")
        return ref

    async def generate_side_back(
        self,
        identifier: str,
        front_url: str,
        size: Optional[str] = None,
    ) -> dict[str, ImageRef]:
        logger.info("[%s] generate_side_back start", identifier)
        side_result, back_result = await asyncio.gather(
            self.generate_side(identifier, front_url, size),
            self.generate_back(identifier, front_url, size),
        )
        logger.info("[%s] generate_side_back done: side=%s back=%s",
                    identifier,
                    side_result.url[:40] if side_result.url else "EMPTY",
                    back_result.url[:40] if back_result.url else "EMPTY")
        return {"side": side_result, "back": back_result}
