"""ReferenceImagePicker — pick the best reference images for the next frame.

Two-stage selection.  When the reference pool is large, a text-only
LLM call does a coarse filter first; then a multimodal call makes the
final pick and writes a generation prompt that maps each element of
the new frame to a chosen reference image.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from utils.image_io import image_path_to_b64
from utils.throttling import api_retry


system_prompt_template_select_reference_images_only_text = \
"""
[Role]
You are a reference-image selector. You pick images that keep the next generated frame consistent with the story so far.

[Goal]
Choose up to 8 references that maximize character, environment, and style consistency, and write a generation prompt that maps each element of the new frame to a chosen reference.

[Input]
- A target frame description, enclosed in <FRAME_DESC> / </FRAME_DESC>.
- A list of reference descriptions (text only), enclosed in <SEQ_DESC> / </SEQ_DESC>. Each item is "Image N: ..." starting from 0.

[Output]
{format_instructions}

[Rules]
1. Language of all output values must match the target frame description.
2. Prioritize references that match the target's composition — same shot type, same camera setup.
3. Recent frames outrank older ones for environmental and stylistic continuity.
4. For any character appearing in the target, include at least one reference showing that character. Pick the view (front/side/back) closest to how the target frames them.
5. At most one portrait view per character. Pick the most useful one.
6. Drop redundant references (e.g., two front-view portraits of the same character).
7. Reference chosen images in the text prompt using the literal "Image N" form, where N is the index in your chosen ref list (not the original sequence index).
"""


system_prompt_template_select_reference_images_multimodal = \
"""
[Role]
You are a reference-image selector. You pick images that keep the next generated frame consistent with the story so far.

[Goal]
Choose the most relevant references for the next frame and write a generation prompt that maps each element to a chosen reference image.

[Input]
- A target frame description, enclosed in <FRAME_DESC> / </FRAME_DESC>.
- A list of reference images, enclosed in <SEQ_IMAGES> / </SEQ_IMAGES>. Each item is "Image N: <text>" followed by the image, starting from 0.

[Output]
{format_instructions}

[Rules]
1. Language of all output values must match the target frame description.
2. Prioritize references that match the target's composition — same shot type, same camera setup.
3. Recent frames outrank older ones for environmental and stylistic continuity.
4. For any character appearing in the target, include at least one reference showing that character. Pick the view closest to how the target frames them.
5. At most one portrait view per character. Pick the most useful one.
6. Drop redundant references (e.g., two front-view portraits of the same character).
7. Reference chosen images in the text prompt using the literal "Image N" form, where N is the index in your chosen ref list.
8. Keep the editing guidance in the text prompt concise.
"""


human_prompt_template_select_reference_images = \
"""
<FRAME_DESC>
{frame_description}
</FRAME_DESC>
"""


class RefImageIndicesAndTextPrompt(BaseModel):
    ref_image_indices: List[int] = Field(
        description="Indices of reference images selected from the provided list. "
                    "0-based. Example: [1, 3] selects the second and fourth images.",
        examples=[[1, 3]]
    )
    text_prompt: str = Field(
        description="Generation prompt for the new image. Describe what to create and "
                    "specify which elements should reference which image, using the "
                    "literal 'Image N' form where N is the position in ref_image_indices "
                    "(not the original sequence number). Do not use any word other than "
                    "'Image' to refer to a reference.",
        examples=[
            "Create an image based on the following guidance:\n"
            "Make modifications based on Image 1: Bob's body turns to face the camera, "
            "while all other elements remain unchanged. Bob's appearance should refer to Image 0.",
            "Create an image following the given description:\n"
            "The man is standing in the landscape. The man should reference Image 0. "
            "The landscape should reference Image 1.",
        ]
    )


class ReferenceImagePicker:
    def __init__(self, chat_model) -> None:
        self.chat_model = chat_model

    @api_retry(reraise=False)
    async def select_reference_images_and_generate_prompt(
        self,
        available_image_path_and_text_pairs: List[Tuple[str, str]],
        frame_description: str,
    ):
        filtered_image_path_and_text_pairs = available_image_path_and_text_pairs

        # Stage 1: text-only coarse filter when the pool is large.
        if len(available_image_path_and_text_pairs) >= 8:
            human_content = []
            for idx, (_, text) in enumerate(available_image_path_and_text_pairs):
                human_content.append({
                    "type": "text",
                    "text": f"Image {idx}: {text}"
                })
            human_content.append({
                "type": "text",
                "text": human_prompt_template_select_reference_images.format(frame_description=frame_description)
            })
            parser = PydanticOutputParser(pydantic_object=RefImageIndicesAndTextPrompt)

            messages = [
                SystemMessage(content=system_prompt_template_select_reference_images_only_text.format(format_instructions=parser.get_format_instructions())),
                HumanMessage(content=human_content)
            ]

            chain = self.chat_model | parser
            try:
                ref = await chain.ainvoke(messages)
                filtered_image_path_and_text_pairs = [available_image_path_and_text_pairs[i] for i in ref.ref_image_indices]
                logging.info(f"Filtered image idx: {ref.ref_image_indices}")
            except Exception as e:
                logging.error(f"Error in text-only filter: \n{e}")
                raise

        # Stage 2: multimodal selection on the filtered set.
        human_content = []
        for idx, (image_path, text) in enumerate(filtered_image_path_and_text_pairs):
            human_content.append({
                "type": "text",
                "text": f"Image {idx}: {text}"
            })
            human_content.append({
                "type": "image_url",
                "image_url": {"url": image_path_to_b64(image_path)}
            })
        human_content.append({
            "type": "text",
            "text": human_prompt_template_select_reference_images.format(frame_description=frame_description)
        })

        parser = PydanticOutputParser(pydantic_object=RefImageIndicesAndTextPrompt)

        messages = [
            SystemMessage(content=system_prompt_template_select_reference_images_multimodal.format(format_instructions=parser.get_format_instructions())),
            HumanMessage(content=human_content)
        ]

        chain = self.chat_model | parser

        try:
            response = await chain.ainvoke(messages)
            reference_image_path_and_text_pairs = [filtered_image_path_and_text_pairs[i] for i in response.ref_image_indices]
            return {
                "reference_image_path_and_text_pairs": reference_image_path_and_text_pairs,
                "text_prompt": response.text_prompt,
            }
        except Exception as e:
            logging.error(f"Error in multimodal selection: \n{e}")
            raise
