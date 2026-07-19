from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, List, Optional

from backend.utils.logging import setup_logger
from backend.pipeline.conductor import (
    END_FRAME,
    START_FRAME,
)
from backend.clients.image import Image
from backend.clients.llm import LLM
from backend.clients.errors import ContentFilterError
from backend.core.types import ImageRef
from backend.db.storyboards import get_shot_by_project_scene
from backend.schemas.models import ModelConfig
from backend.services.reference_picker import ReferencePicker
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from backend.schemas.character import CharacterRead
    from backend.utils.paths import SceneScope

logger = setup_logger("shot_image_generator")

_FILTER_REWRITE_PROMPT = """\
The following image generation prompt was rejected by a content safety filter.
Please rewrite it to be safe for generative image models while preserving the visual intent, composition, and key details. Remove or rephrase any elements that could trigger safety filters, but keep the core visual description intact.

Original prompt:
{prompt}

Rewritten prompt (output only the rewritten prompt, no explanation):"""


class ImageGenerator:
    def __init__(
        self,
        image_config: ModelConfig,
        chat_config: ModelConfig,
        size: str = "1024x576",
        vision_config: ModelConfig | None = None,
        ratio: str = "",
    ):
        self._size = size
        self._ratio = ratio
        self._image_config = image_config
        self._chat_config = chat_config

        self._ref_selector = ReferencePicker(
            llm_config=chat_config,
            vision_config=vision_config or chat_config,
        )

    @staticmethod
    async def _get_existing_url(
        scene: "SceneScope",
        shot_idx: int,
        frame_type: str,
    ) -> str:
        col = {"start_frame.png": "start_frame_url", "end_frame.png": "end_frame_url"}.get(
            frame_type)
        if not col:
            return ""
        shot = await get_shot_by_project_scene(
            scene.project_id, scene.scene_idx, shot_idx)
        return shot.get(col, "") if shot else ""

    async def generate(
        self,
        shot_idx: int,
        frame_type: str,
        frame_description: str,
        vis_char_idxs: List[int],
        characters: List["CharacterRead"],
        scene: "SceneScope",
        extra_references: Optional[List[ImageRef]] = None,
    ) -> ImageRef:
        from backend.utils.refs import collect_character_references

        frame_path = scene.shot(shot_idx).path(frame_type)
        logger.info("[shot=%d] ImageGenerator.generate: frame_type=%s, path=%s",
                    shot_idx, frame_type, frame_path)

        if os.path.exists(frame_path):
            url = await self._get_existing_url(scene, shot_idx, frame_type)
            logger.info("[shot=%d] %s already exists on disk, reusing (url=%s)",
                        shot_idx, frame_type, url)
            local_url = scene.shot(shot_idx).url(frame_type)
            return ImageRef(url=url, local_url=local_url, prompt=frame_description)

        reference_candidates = collect_character_references(
            vis_char_idxs, characters)
        if extra_references:
            logger.info("[shot=%d] adding %d extra references",
                        shot_idx, len(extra_references))
            reference_candidates.extend(extra_references)

        logger.info("[shot=%d] reference candidates: %s, %s",
                    shot_idx, reference_candidates, characters)

        logger.info("[shot=%d] building prompt with %d reference candidates",
                    shot_idx, len(reference_candidates))
        generation_prompt, reference_images = await self._ref_selector.build_prompt(
            reference_candidates=reference_candidates,
            frame_description=frame_description,
        )
        logger.info("[shot=%d] prompt built, %d reference images selected",
                    shot_idx, len(reference_images))

        logger.info("[shot=%d] calling AI image generation...", shot_idx)
        result = await self._generate_single_image(
            prompt=generation_prompt,
            reference_images=reference_images,
            save_path=str(frame_path),
        )
        logger.info("[shot=%d] %s AI generation completed: url=%s",
                    shot_idx, frame_type, result.url)
        result.local_url = scene.shot(shot_idx).url(frame_type)
        return result

    async def _generate_single_image(
        self,
        prompt: str,
        reference_images: List[ImageRef],
        save_path: str,
        size: Optional[str] = None,
    ) -> ImageRef:
        size = size or self._size
        logger.info("Generating image, save_path=%s, size=%s", save_path, size)

        if not self._image_config.model:
            raise RuntimeError("Image generator is not configured")

        payload: dict = {"prompt": prompt, "n": 1, "size": size}
        if self._ratio:
            payload["ratio"] = self._ratio
        if reference_images:
            payload["reference_images"] = [
                {"url": r.url} for r in reference_images]
        if save_path:
            payload["save_path"] = save_path

        result, _ = await Image.generate(
            self._image_config.model, payload, self._image_config.api_key, self._image_config.base_url,
            on_filter=self._rewrite_prompt_on_filter,
        )
        data = result.get("data", [])
        if not data:
            raise ValueError(f"No image data in response: {result}")
        url = data[0].get("url", "")
        if not url:
            raise ValueError(f"No url in response data: {data[0]}")
        return ImageRef(url=url, prompt=prompt)

    async def _rewrite_prompt_on_filter(self, error: ContentFilterError) -> str:
        logger.warning(
            "[rewrite] content filter rejected prompt, rewriting via LLM: %s", error)
        messages = [
            SystemMessage(
                content="You are a prompt rewriter for image generation."),
            HumanMessage(content=_FILTER_REWRITE_PROMPT.format(
                prompt=error.prompt)),
        ]
        rewritten = await LLM.chat(
            self._chat_config.model, messages,
            self._chat_config.api_key, self._chat_config.base_url,
            project_id=0,
            task_id=f"rewrite-{hash(error.prompt)}",
        )
        rewritten = rewritten.strip().strip('"\'')
        logger.info("[rewrite] prompt rewritten: %.100s -> %.100s",
                    error.prompt, rewritten)
        return rewritten
