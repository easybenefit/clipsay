"""PortraitGenerator — render front / side / back reference sheets for a character.

The three reference views (front, side, back) are generated with a
consistent visual style so the rest of the pipeline can pull any view
as a reference image and keep the character looking like the same
person across shots.
"""

from __future__ import annotations

from schemas import CharacterInScene, ImageOutput
from utils.throttling import api_retry


prompt_template_front_portrait = \
"""
Full-body front-view reference portrait of {identifier}. Centered, occupying most of the frame. Gazing straight ahead. Standing with arms relaxed at sides. Natural expression. Pure white background. Character design sheet.

Static features: {static_features}
Dynamic features: {dynamic_features}
Visual style: {style}
"""


prompt_template_side_portrait = \
"""
Full-body side-view reference portrait of {identifier} (facing left, profile). Centered, occupying most of the frame. Standing with arms relaxed at sides. Pure white background. Character design sheet, visually consistent with the provided front portrait. Visual style: {style}.
"""


prompt_template_back_portrait = \
"""
Full-body back-view reference portrait of {identifier} (facing away, no facial features visible). Centered, occupying most of the frame. Standing with arms relaxed at sides. Pure white background. Character design sheet, visually consistent with the provided front portrait. Visual style: {style}.
"""


class PortraitGenerator:
    def __init__(self, image_generator) -> None:
        self.image_generator = image_generator

    @api_retry(reraise=True)
    async def generate_front_portrait(
        self,
        character: CharacterInScene,
        style: str,
    ) -> ImageOutput:
        prompt = prompt_template_front_portrait.format(
            identifier=character.identifier_in_scene,
            static_features=character.static_features,
            dynamic_features=character.dynamic_features,
            style=style,
        )
        return await self.image_generator.generate_single_image(prompt=prompt)

    @api_retry(reraise=True)
    async def generate_side_portrait(
        self,
        character: CharacterInScene,
        front_image_path: str,
        style: str,
    ) -> ImageOutput:
        prompt = prompt_template_side_portrait.format(
            identifier=character.identifier_in_scene,
            style=style,
        )
        return await self.image_generator.generate_single_image(
            prompt=prompt,
            reference_image_paths=[front_image_path],
        )

    @api_retry(reraise=True)
    async def generate_back_portrait(
        self,
        character: CharacterInScene,
        front_image_path: str,
        style: str,
    ) -> ImageOutput:
        prompt = prompt_template_back_portrait.format(
            identifier=character.identifier_in_scene,
            style=style,
        )
        return await self.image_generator.generate_single_image(
            prompt=prompt,
            reference_image_paths=[front_image_path],
        )
