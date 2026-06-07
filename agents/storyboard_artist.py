"""StoryboardArtist — design a scene's shot list and decompose each shot.

The class bundles two related LLM tasks:

* :meth:`design_storyboard` — turn a scene script + cast into a list of
  shot briefs.
* :meth:`decompose_visual_description` — expand a single shot's
  visual description into a :class:`ShotSpec` with first frame, last
  frame, and motion.
"""

from __future__ import annotations

import asyncio
from typing import List, Literal, Optional

from langchain.chat_models.base import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from schemas import CharacterInScene, ShotBrief, ShotSpec
from utils.throttling import api_retry


system_prompt_template_design_storyboard = \
"""
[Role]
You are a storyboard artist. You turn a written scene into a sequence of filmable shots.

[Goal]
Design a complete storyboard for a single scene — each shot has a clear narrative purpose, a distinct visual, and optional dialogue.

[Input]
- A scene script, enclosed in <SCRIPT> / </SCRIPT>. Covers one scene only.
- A character list, enclosed in <CHARACTERS> / </CHARACTERS>.
- An optional user requirement, enclosed in <USER_REQUIREMENT> / </USER_REQUIREMENT>. May include target audience, style, max shot count, or other notes.

[Output]
{format_instructions}

[Rules]
1. Language of all output values must match the script.
2. Every shot serves a clear purpose (establish setting, show relationship, capture reaction, etc.).
3. Use cinematic language deliberately: close-ups for emotion, wide shots for context, varied angles to direct attention.
4. Reuse an existing camera setup when shot size, angle, and focus don't change. Introduce a new one only when the view genuinely shifts. A camera that has undergone major movement cannot be reused.
5. Character names must match the character list. Enclose names in angle brackets in visual descriptions (e.g., <Alice>), but never in dialogue or speaker fields.
6. When describing visible elements, always specify their position in the frame. Never describe elements that aren't on screen in this shot.
7. Avoid unsafe content. Use indirect methods (sound, suggestion) where needed, and substitute sensitive elements (e.g., ketchup for blood).
8. At most one line of dialogue per character per shot. Each line maps to a specific shot.
9. Each shot's description is self-contained. No cross-references.
10. When a shot focuses on a character, name the body part in focus.
11. Always indicate the direction a character is facing.
"""


human_prompt_template_design_storyboard = \
"""
<SCRIPT>
{script_str}
</SCRIPT>

<CHARACTERS>
{characters_str}
</CHARACTERS>

<USER_REQUIREMENT>
{user_requirement_str}
</USER_REQUIREMENT>
"""


system_prompt_template_decompose_visual_description = \
"""
[Role]
You are a shot deconstruction specialist. You split a single shot's visual description into three parts: a static first frame, a static last frame, and the dynamic motion between them.

[Goal]
Given a visual description and a character list, emit a ShotSpec with the two frame snapshots and the motion between them.

[Input]
- A visual description of a single shot, enclosed in <VISUAL_DESC> / </VISUAL_DESC>. Typically contains starting state, motion, and ending state.
- A character list, enclosed in <CHARACTERS> / </CHARACTERS>. Each entry: identifier and feature description.

[Output]
{format_instructions}

[Rules]
1. Language of all output values must match the input.
2. First and last frame descriptions are pure snapshots. No ongoing actions. "He is about to stand up" is invalid; "He sits on the chair, leaning slightly forward" is valid.
3. In the motion description, separate camera movement from on-screen movement. Use precise cinematic terminology (dolly, pan, tilt, zoom, track, etc.).
4. In the motion description, never use character names directly. Refer to characters by their visible features (e.g., "the woman (short hair, green dress) walks toward the camera").
5. The last frame must be logically consistent with the first frame and the motion. Every action in the motion section must be reflected in the last frame.
6. If the input is ambiguous, fill in plausible detail so all three sections are complete. Core elements stay faithful to the input.
7. Concise, descriptive language. No metaphors, no emotional flourishes. Every word should help the renderer visualize the shot.
8. First and last frame descriptions include shot type, angle, and composition.
9. Variation within a shot is one of:
   - **large** — dramatic composition change (e.g., wide to close-up with significant camera move, drone across a city).
   - **medium** — new character appears, or a character turns to face the camera.
   - **small** — expression change, mild pose change, modest camera move (pan, tilt, track).
10. Always indicate the direction each character is facing.
11. The first shot in any sequence establishes the overall environment using the widest practical shot.
12. Use as few camera setups as possible.
"""


human_prompt_template_decompose_visual_description = \
"""
<VISUAL_DESC>
{visual_desc}
</VISUAL_DESC>

<CHARACTERS>
{characters_str}
</CHARACTERS>
"""


class ShotDecomposition(BaseModel):
    ff_desc: str = Field(
        description="A detailed description of the first frame of the shot, capturing "
                    "the initial visual elements and composition.",
    )
    ff_vis_char_idxs: List[int] = Field(
        description="Indices of characters visible in the first frame, corresponding to the input character list.",
        examples=[[0], [1], [0, 1], []]
    )
    lf_desc: str = Field(
        description="A detailed description of the last frame of the shot, capturing the concluding visual elements and composition.",
    )
    lf_vis_char_idxs: List[int] = Field(
        description="Indices of characters visible in the last frame.",
        examples=[[0], [1], [0, 1], []]
    )
    motion_desc: str = Field(
        description="The motion description. Describe dynamic visual changes (camera movement and on-screen movement).",
        examples=[
            "Static camera. The woman (short hair, green dress) walks toward the camera.",
            "Dolly in from medium shot to close-up. The man (beard, white T-shirt) smiles at the camera.",
        ]
    )
    variation_type: Literal["large", "medium", "small"] = Field(
        description="Degree of change between the first and last frame.",
    )
    variation_reason: str = Field(
        description="Reason for the variation type.",
        examples=[
            "Smooth transition from sky to ground. Content changes dramatically, so variation is large.",
            "A new character appears in the last frame with no major composition change. Variation is medium.",
            "Only minor changes in composition. Variation is small.",
            "Only the character's expression changes. Variation is small.",
        ],
    )


class StoryboardArtist:
    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    @api_retry(reraise=False)
    async def design_storyboard(
        self,
        script: str,
        characters: List[CharacterInScene],
        user_requirement: Optional[str] = None,
        retry_timeout: int = 150,
    ) -> List[ShotBrief]:
        class StoryboardResponse(BaseModel):
            storyboard: List[ShotBrief] = Field(
                description="A complete storyboard of the scene, including the visual and audio description of each shot.",
            )

        script_str = script.strip()
        characters_str = "\n".join([f"Character {index}: {char}" for index, char in enumerate(characters)])
        user_requirement_str = user_requirement.strip() if user_requirement else ""

        parser = PydanticOutputParser(pydantic_object=StoryboardResponse)
        messages = [
            ('system', system_prompt_template_design_storyboard.format(format_instructions=parser.get_format_instructions())),
            ('human', human_prompt_template_design_storyboard.format(script_str=script_str, characters_str=characters_str, user_requirement_str=user_requirement_str)),
        ]
        chain = self.chat_model | parser
        response: StoryboardResponse = await asyncio.wait_for(
            chain.ainvoke(messages),
            timeout=retry_timeout,
        )
        return response.storyboard

    @api_retry(reraise=False)
    async def decompose_visual_description(
        self,
        shot_brief_desc: ShotBrief,
        characters: List[CharacterInScene],
        retry_timeout: int = 150,
    ) -> ShotSpec:
        parser = PydanticOutputParser(pydantic_object=ShotDecomposition)
        prompt_template = ChatPromptTemplate.from_messages(
            [
                ('system', system_prompt_template_decompose_visual_description),
                ('human', human_prompt_template_decompose_visual_description),
            ]
        )
        chain = prompt_template | self.chat_model | parser

        visual_desc = shot_brief_desc.visual_desc.strip()
        characters_str = "\n".join(
            [f"{char.identifier_in_scene}: (static) {char.static_features}; (dynamic) {char.dynamic_features}" for char in characters]
        )

        decomposition: ShotDecomposition = await asyncio.wait_for(
            chain.ainvoke(
                input={
                    "format_instructions": parser.get_format_instructions(),
                    "visual_desc": visual_desc,
                    "characters_str": characters_str,
                },
            ),
            timeout=retry_timeout,
        )

        return ShotSpec(
            idx=shot_brief_desc.idx,
            is_last=shot_brief_desc.is_last,
            cam_idx=shot_brief_desc.cam_idx,
            visual_desc=shot_brief_desc.visual_desc,
            variation_type=decomposition.variation_type,
            variation_reason=decomposition.variation_reason,
            ff_desc=decomposition.ff_desc,
            ff_vis_char_idxs=decomposition.ff_vis_char_idxs,
            lf_desc=decomposition.lf_desc,
            lf_vis_char_idxs=decomposition.lf_vis_char_idxs,
            motion_desc=decomposition.motion_desc,
            audio_desc=shot_brief_desc.audio_desc,
        )
