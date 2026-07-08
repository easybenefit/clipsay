from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import List, Tuple

from PIL import Image
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from tenacity import retry, stop_after_attempt

from backend.clients.llm import LLM
from backend.utils.logging import setup_logger
from backend.core.types import ImageRef
from backend.schemas.models import ModelConfig
from backend.schemas import FrameRecord, ReferenceSelection
from backend.utils.retry import log_retry_failure

logger = setup_logger("reference_picker")


# ===================================================================
#  ReferencePicker
# ===================================================================

# ---------------------------------------------------------------------------
#  System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEXT_ONLY = """
[角色]
你是一名专业的视觉创作顾问，精通多模态图像分析与推理，深谙影视工业前期概念图与分镜的视觉匹配逻辑。

[任务]
根据用户提供的目标帧文本描述，从一组参考图像描述（包括多个角色造型参考图及前序已生成的分镜图像）中，智能筛选最合适的参考图像，以确保后续生成图像严格满足以下一致性：
- 角色一致性：生成角色的外观（性别、人种、年龄、五官、发型、体型）、着装、表情与姿态须与参考图像描述高度吻合。
- 环境一致性：生成图像的场景（背景、光源方向、氛围、空间布局）须与前序已生成分镜的环境保持连贯。
- 风格一致性：生成图像的视觉风格（如写实、卡通、电影感、色彩倾向）须与参考图像描述协调统一。

[输入]
你将接收到目标帧的文本描述以及一组参考图像描述。
- 目标帧文本描述包裹在 <FRAME_DESC> 与 </FRAME_DESC> 标签内。
- 参考图像描述序列包裹在 <SEQ_DESC> 与 </SEQ_DESC> 标签内。每条描述附有前缀索引，从 0 开始。

以下是输入格式示例：
<FRAME_DESC>
[机位1] 过肩镜头，机位在 Alice 身后。Alice 靠近摄影机一侧，仅肩部出现在画框左下角。Bob 在远离摄影机一侧，位于画面中央偏右。Bob 认出 Alice，表情由惊讶转为欣喜。
</FRAME_DESC>

<SEQ_DESC>
Image 0: Alice 的正面造型参考图。
Image 1: Bob 的正面造型参考图。
Image 2: [机位0] 超市货架通道的中景。Alice 与 Bob 以侧面示人，面朝画面右侧。Bob 在画右，Alice 在画左。Alice 低头推着购物车紧随 Bob 身后，不慎撞到他的脚后跟。
Image 3: [机位1] 过肩镜头，机位在 Alice 身后。Alice 靠近摄影机一侧，仅肩部出现在画框左下角。Bob 在远离摄影机一侧，位于画面中央偏右。Bob 迅速转身，神情由淡漠转为惊讶。
Image 4: [机位2] 过肩镜头，机位在 Bob 身后。Bob 靠近摄影机一侧，仅肩部出现在画框右下角。Alice 在远离摄影机一侧，位于画面中央偏左。Alice 先低头，抬首准备道歉，认出熟人后表情转为意外。
</SEQ_DESC>

[输出]
你需要从参考图像描述中挑选至多 8 张最相关的参考图，将其索引填入输出的 selected_indices 字段。同时，生成一条文本提示描述待创建图像，明确指出生成图像中哪些元素应参照哪张参考图（及其中的哪些元素）。

{format_instructions}

[指南]
- 确保所有输出值（不含键名）的语言与目标帧描述的语言一致。
- 参考图像描述可能以不同角度、不同造型或不同场景呈现同一角色，请选择与用户描述版本最接近的参考图。
- 优先选取构图相似的图像描述（如同一机位拍摄的镜头）。
- 前序帧图像按时间顺序排列，优先选择更靠近序列末尾（时间更近）的图像。
- 所选参考图像描述应尽量精炼，避免冗余。例如，若 Image 3 已从正面展示 Bob 的面部特征，而 Image 1 同样是 Bob 的正面造型参考图，则 Image 1 冗余，不应选取。
- 当帧描述中出现新角色时，优先选取其角色造型参考图（若有），以确保外貌描绘准确。注意角色面向摄影机是正面、侧面还是背面，选择最合适的视图作为该角色的参考图像。
- 对于同一角色的多视图造型参考图（正面、侧面、背面），最多只能选择一张。根据帧描述选取最合适者。例如，描绘角色侧面时，优先选用该角色的侧面造型图。
- 最多选择 **8** 张最优参考图像。
"""

SYSTEM_PROMPT_MULTIMODAL = """
[角色]
你是一名专业的视觉创作顾问，精通多模态图像分析与推理，深谙影视工业前期概念图与分镜的视觉匹配逻辑。

[任务]
根据用户提供的目标帧文本描述，从一组参考图像库（包括多个角色造型参考图及前序已生成的分镜图像）中，智能筛选最合适的参考图像，以确保后续生成图像严格满足以下一致性：
- 角色一致性：生成角色的外观（性别、人种、年龄、五官、发型、体型）、着装、表情与姿态须与参考图像高度吻合。
- 环境一致性：生成图像的场景（背景、光源方向、氛围、空间布局）须与前序已生成分镜的环境保持连贯。
- 风格一致性：生成图像的视觉风格（如写实、卡通、电影感、色彩倾向）须与参考图像及现有图像协调统一。

[输入]
你将接收到目标帧的文本描述以及一组参考图像（含描述）。
- 目标帧文本描述包裹在 <FRAME_DESC> 与 </FRAME_DESC> 标签内。
- 参考图像序列包裹在 <SEQ_IMAGES> 与 </SEQ_IMAGES> 标签内。每张参考图像附有文本描述，图像索引从 0 开始。

以下是输入格式示例：
<FRAME_DESC>
[机位1] 过肩镜头，机位在 Alice 身后。<Alice> 靠近摄影机一侧，仅肩部出现在画框左下角。<Bob> 在远离摄影机一侧，位于画面中央偏右。<Bob> 认出 <Alice>，表情由惊讶转为欣喜。
</FRAME_DESC>

<SEQ_IMAGES>
Image 0: Alice 的正面造型参考图。
[Image 0 此处为图像]
Image 1: Bob 的正面造型参考图。
[Image 1 此处为图像]
Image 2: [机位0] 超市货架通道的中景。Alice 与 Bob 以侧面示人，面朝画面右侧。Bob 在画右，Alice 在画左。Alice 低头推着购物车紧随 Bob 身后，不慎撞到他的脚后跟。
[Image 2 此处为图像]
Image 3: [机位1] 过肩镜头，机位在 Alice 身后。Alice 靠近摄影机一侧，仅肩部出现在画框左下角。Bob 在远离摄影机一侧，位于画面中央偏右。Bob 以背影示人。
[Image 3 此处为图像]
Image 4: [机位2] 过肩镜头，机位在 Bob 身后。Bob 靠近摄影机一侧，仅肩部出现在画框右下角。Alice 在远离摄影机一侧，位于画面中央偏左。Alice 先低头，抬首准备道歉，认出熟人后表情转为意外。
</SEQ_IMAGES>

[输出]
你需要根据用户描述选取最相关的参考图像，将其索引填入输出的 `selected_indices` 字段。同时，生成一条文本提示描述待创建图像，明确指出生成图像中哪些元素应参照哪张图像（及其中哪些元素）。

{format_instructions}

[指南]
- 确保所有输出值（不含键名）的语言与目标帧描述的语言一致。
- 参考图像（及其描述）可能以不同角度、不同造型或不同场景呈现同一角色，请选择与用户描述版本最接近的参考图。
- 优先选取构图相似的图像（如同一机位拍摄的镜头）。
- 前序帧图像按时间顺序排列，优先选择更靠近序列末尾（时间更近）的图像。
- 所选参考图像描述应尽量精炼，避免冗余。例如，若 Image 3 已从正面展示 Bob 的面部特征，而 Image 1 同样是 Bob 的正面造型参考图，则 Image 1 冗余，不应选取。
- 对于同一角色的多视图造型参考图（正面、侧面、背面），最多只能选择一张。根据帧描述选取最合适者。例如，描绘角色侧面时，优先选用该角色的侧面造型图。
- 最多选择 **8** 张最优参考图像。
- 指导图像编辑的文本提示应尽量简洁。
"""

HUMAN_PROMPT_TEMPLATE = """
<FRAME_DESC>
{frame_description}
</FRAME_DESC>
"""

# Max candidates the text-only filter should produce.
MAX_VISION_CANDIDATES = 8


# ===================================================================
#  ReferencePicker
# ===================================================================

class ReferencePicker:
    """Two-stage reference image selector.

    Stage 1 (text-only LLM, when candidates > *MAX_VISION_CANDIDATES*):
      Uses *llm_config* to rank the candidates' *descriptions* alone, narrowing
      them to at most *MAX_VISION_CANDIDATES* entries.

    Stage 2 (vision-capable LLM):
      Uses *vision_config* to inspect the actual images (base64) and pick the
      single best reference, producing a generation prompt.

    Separating the two stages lets you use a cheap / fast text model for the
    initial coarse filter and reserve the expensive vision model for the final
    fine-grained selection.
    """

    def __init__(
        self,
        llm_config: ModelConfig,
        vision_config: ModelConfig,
    ) -> None:
        self._llm = llm_config
        self._vision = vision_config

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), after=log_retry_failure)
    async def select_references(
        self,
        reference_candidates: List[ImageRef],
        frame_description: str,
    ) -> dict:
        """Return ``{"references": [...], "generation_prompt": "..."}``."""
        # Stage 1: coarse text-only filter when there are too many candidates.
        if len(reference_candidates) > MAX_VISION_CANDIDATES:
            logger.info(
                "Candidates=%d > %d, applying text-only LLM filter",
                len(reference_candidates), MAX_VISION_CANDIDATES,
            )
            candidates = await self._filter_by_text(reference_candidates, frame_description)
        else:
            candidates = reference_candidates

        # Stage 2: vision-based final selection.
        return await self._select_with_vision(candidates, frame_description)

    async def build_prompt(
        self,
        reference_candidates: List[ImageRef],
        frame_description: str,
    ) -> Tuple[str, List[ImageRef]]:
        """Convenience wrapper: select references and format final prompt."""
        result = await self.select_references(
            reference_candidates=reference_candidates,
            frame_description=frame_description,
        )
        selected: List[ImageRef] = result["references"]
        prompt: str = result["generation_prompt"]

        if selected:
            prefix = "\n".join(
                f"Image {i}: {ref.prompt}" for i, ref in enumerate(selected)
            )
            prompt = f"{prefix}\n{prompt}"

        return prompt, selected

    # ------------------------------------------------------------------
    #  Stage 1 — text-only coarse filter  (uses self._llm)
    # ------------------------------------------------------------------

    async def _filter_by_text(
        self,
        candidates: List[ImageRef],
        frame_description: str,
    ) -> List[ImageRef]:
        """Use the text-only LLM to narrow *candidates* to ≤ 8 entries."""
        content = [
            {"type": "text", "text": f"Image {idx}: {ref.prompt}"}
            for idx, ref in enumerate(candidates)
        ]
        content.append({
            "type": "text",
            "text": HUMAN_PROMPT_TEMPLATE.format(frame_description=frame_description),
        })

        parser = PydanticOutputParser(pydantic_object=ReferenceSelection)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_TEXT_ONLY.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(content=content),
        ]

        try:
            raw = await LLM.chat(self._llm.model, messages, self._llm.api_key, self._llm.base_url)
            result = parser.parse(raw)
            logger.info("Text-filter selected indices: %s", result.selected_indices)
            return [candidates[i] for i in result.selected_indices]
        except Exception:
            logger.exception("Text-only LLM filter failed")
            raise

    # ------------------------------------------------------------------
    #  Stage 2 — vision-based final selection  (uses self._vision)
    # ------------------------------------------------------------------

    async def _select_with_vision(
        self,
        candidates: List[ImageRef],
        frame_description: str,
    ) -> dict:
        """Use the vision-capable LLM to pick the best reference(s)."""
        content: list = []
        for idx, ref in enumerate(candidates):
            content.append({
                "type": "text",
                "text": f"Image {idx}: {ref.prompt}",
            })
            content.append({
                "type": "image_url",
                "image_url": {"url": ref.url},
            })
        content.append({
            "type": "text",
            "text": HUMAN_PROMPT_TEMPLATE.format(frame_description=frame_description),
        })

        parser = PydanticOutputParser(pydantic_object=ReferenceSelection)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT_MULTIMODAL.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(content=content),
        ]

        try:
            raw = await LLM.chat(self._vision.model, messages, self._vision.api_key, self._vision.base_url)
            result = parser.parse(raw)
            n = len(candidates)
            selected = [candidates[i] for i in result.selected_indices if 0 <= i < n]
            logger.info("Vision selected %d reference(s)", len(selected))
            return {"references": selected, "generation_prompt": result.generation_prompt}
        except Exception:
            logger.exception("Vision-based selection failed")
            raise
