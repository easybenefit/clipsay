"""ImageScorer — pick the best candidate image for a target frame.

Given a set of reference images and a set of candidate images, the
LLM picks the candidate that best matches the target description
across three axes: character consistency, spatial consistency, and
description accuracy.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from utils.image_io import image_path_to_b64
from utils.throttling import api_retry


system_prompt_template_select_most_consistent_image = \
"""
[Role]
You are an image-consistency judge. You pick the candidate that best matches a target description while staying visually consistent with the references.

[Goal]
Pick the single candidate that most faithfully realizes the target description.

[Input]
- Reference images: each prefixed with a short text caption ("Reference Image N: ..."). Indices start at 0.
- Candidate images: each prefixed with "Candidate Image N". Indices start at 0.
- A target description, enclosed in <TARGET_DESCRIPTION_START> / <TARGET_DESCRIPTION_END>.

Score each candidate on three axes:
1. **Character consistency** — gender, ethnicity, age, facial features, body shape, outfit, hairstyle match the references.
2. **Spatial consistency** — relative positions, scene layout, perspective, and orientation match the references.
3. **Description accuracy** — the candidate reflects the actions, objects, and setting in the target description. Editing-instruction phrasing should be ignored; treat it as the desired end state.

[Output]
{format_instructions}

[Rules]
1. Treat the target description as the goal, not as an editing directive.
2. Prefer candidates with no white borders, black edges, or framing artifacts.
3. If no candidate is perfect, pick the best and note its shortcomings in the reason field.
4. Base all judgments on objective comparisons between images; avoid subjective preference.
5. Ensure every key element named in the target description is present in the selected image.
"""


human_prompt_template_select_most_consistent_image = \
"""
<TARGET_DESCRIPTION_START>
{target_description}
<TARGET_DESCRIPTION_END>
"""


class BestImageSelection(BaseModel):
    best_image_index: int = Field(
        ...,
        description="The index of the best image."
    )
    reason: str = Field(
        ...,
        description="The reason why the image is the best."
    )


class ImageScorer:
    def __init__(self, chat_model) -> None:
        self.chat_model = chat_model

    @api_retry(reraise=False)
    async def __call__(
        self,
        reference_image_path_and_text_pairs: List[Tuple[str, str]],
        target_description: str,
        candidate_image_paths: List[str],
    ) -> str:
        if not candidate_image_paths:
            logging.warning("No candidate images provided; skipping best image selection")
            raise ValueError("No candidate images to select from")

        logging.info(f"Selecting the best image from candidates: {candidate_image_paths}")

        human_content = []
        for idx, (ref_image_path, text) in enumerate(reference_image_path_and_text_pairs):
            human_content.append({
                "type": "text",
                "text": f"Reference Image {idx}: {text}"
            })
            human_content.append({
                "type": "image_url",
                "image_url": {"url": image_path_to_b64(ref_image_path, mime=True)}
            })

        for idx, candidate_image_path in enumerate(candidate_image_paths):
            human_content.append({
                "type": "text",
                "text": f"Candidate Image {idx}"
            })
            human_content.append({
                "type": "image_url",
                "image_url": {"url": image_path_to_b64(candidate_image_path, mime=True)}
            })
        human_content.append({
            "type": "text",
            "text": human_prompt_template_select_most_consistent_image.format(target_description=target_description)
        })

        parser = PydanticOutputParser(pydantic_object=BestImageSelection)

        messages = [
            SystemMessage(content=system_prompt_template_select_most_consistent_image.format(format_instructions=parser.get_format_instructions())),
            HumanMessage(content=human_content)
        ]

        chain = self.chat_model | parser

        response = await chain.ainvoke(messages)
        idx = response.best_image_index
        if not isinstance(idx, int) or idx < 0 or idx >= len(candidate_image_paths):
            logging.warning(f"Received invalid best_image_index={idx}; defaulting to 0")
            idx = 0
        best_image_path = candidate_image_paths[idx]
        logging.info(f"Best image selected: {best_image_path}")
        logging.info(f"Selection reason: {response.reason}")
        return best_image_path
