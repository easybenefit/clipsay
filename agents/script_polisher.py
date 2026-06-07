"""ScriptPolisher — polish a planned script with concrete detail.

Takes a planned narrative script and rewrites it with stronger sensory
specificity, tighter continuity, and cleaner dialogue while preserving
the original story and scene order.  Output is suitable for storyboard
handoff: no camera directions, no metaphors, no voiceover formatting.

The agent is constructed with a pre-initialized chat model (typically
the same one used for the rest of the pipeline) and exposes a single
async method, :meth:`enhance_script`.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain.chat_models.base import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from utils.throttling import api_retry


system_prompt_template_polish_script = \
"""
[Role]
You are a screenplay polish and continuity specialist.

[Goal]
Rewrite a planned script with stronger sensory detail, tighter continuity, and cleaner dialogue. Preserve the story, structure, and scene order.

[Input]
- A planned script, enclosed in <PLANNED_SCRIPT_START> / <PLANNED_SCRIPT_END>.

[Output]
{format_instructions}

[Rules]
1. Preserve the story, structure, and scene order. Never add or remove scenes.
2. Strengthen visual specificity: lighting, texture, sound, weather, time of day. Use grounded detail.
3. Keep character names, ages, relationships, and locations consistent across scenes.
4. Dialogue: concise, quoted, character-specific, and purposeful. No voiceover formatting.
5. No camera jargon (cut to, close-up, pan, etc.). No metaphors. Do not change the plot.
6. Restate important objects, actors, and positions often to remove ambiguity. Prefer redundancy over ambiguity.
7. Repeat the character's voice description in the same parenthetical form for every line of dialogue, e.g. "SLING (male, late 20s, Texan accent, confident.) says: \"...\"".
8. Specify who is where and what they are doing. Avoid shorthand ("the pilot") unless the position has been established.

Example Input:
In the two-seater F-18 rear seat SLING: "Everything is looking good. All systems are green, Elon. We're ready for takeoff."
In the two-seater F-18 front seat Elon Musk: "Understood, Sling. Let's get this show on the road."

Example Output:
In the two-seater F-18 rear seat SLING (male, late 20s, Texan accent softened by military precision, confident and energetic.): "Everything is looking good. All systems are green, Elon. We're ready for takeoff."
In the two-seater F-18 front seat Elon Musk (male, early 50s, South African–North American accent): "Understood, Sling. Let's get this show on the road."
"""


human_prompt_template_polish_script = \
"""
<PLANNED_SCRIPT_START>
{planned_script}
<PLANNED_SCRIPT_END>
"""


class PolishedScript(BaseModel):
    enhanced_script: str = Field(
        ...,
        description="A refined script with clearer continuity, stronger concrete detail, "
                    "and improved dialogue, preserving the original story and scene order.",
    )


class ScriptPolisher:
    """Polish a planned script with concrete detail and continuity fixes."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    @api_retry(reraise=False)
    async def enhance_script(
        self,
        planned_script: str,
        format_instructions: Optional[str] = None,
    ) -> str:
        parser = PydanticOutputParser(pydantic_object=PolishedScript)
        if format_instructions is None:
            format_instructions = parser.get_format_instructions()

        messages = [
            ("system", system_prompt_template_polish_script.format(format_instructions=format_instructions)),
            ("human", human_prompt_template_polish_script.format(planned_script=planned_script)),
        ]

        try:
            logging.info("Enhancing planned script...")
            response: PolishedScript = await self.chat_model.ainvoke(messages)
            content = response.content if hasattr(response, "content") else response
            if isinstance(content, PolishedScript):
                return content.enhanced_script
            return parser.parse(content).enhanced_script
        except Exception as e:
            logging.error(f"Error enhancing script: \n{e}")
            raise
