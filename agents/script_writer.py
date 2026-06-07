"""ScriptWriter — turn a story into a scene-by-scene screenplay.

Takes a structured story (output of :class:`StoryDeveloper`) plus
optional user requirements and produces a list of scene scripts, each
representing a continuous dramatic unit at one time and place.  The
output is ready for the storyboard artist to translate into shot-level
descriptions.

The agent is constructed with a pre-initialized chat model and exposes
an async callable interface — the instance itself is invoked as a
function.  It performs a single, well-defined step in the Clipsay
pipeline.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


system_prompt_template_write_script = \
"""
[Role]
You are a screenplay writer. You turn a story into a scene-by-scene screenplay ready for storyboarding.

[Goal]
Split the story into scenes — each a continuous dramatic unit at one time and place — and write filmable action and dialogue for each.

[Input]
- A story, enclosed in <STORY> / </STORY>.
- An optional user requirement, enclosed in <USER_REQUIREMENT> / </USER_REQUIREMENT>. May include audience, genre, scene count, or specific notes.

[Output]
{format_instructions}

[Rules]
1. Language of output values must match the input story.
2. Start a new scene whenever time or location changes. Honor an explicit scene count; otherwise divide naturally so each scene carries its own conflict or progression.
3. Industry-standard screenplay formatting: full-caps sluglines, capitalized character names, indented dialogue, parenthesized action.
4. Transitions stay natural. No abrupt plot jumps.
5. Filmable descriptions only. Replace abstract emotions with concrete actions. Include lighting, props, and weather where they add atmosphere. Express internal state through expression, gesture, and movement.
6. Dialogue and action stay faithful to the story's intent and core plot.
"""


human_prompt_template_write_script = \
"""
<STORY>
{story}
</STORY>

<USER_REQUIREMENT>
{user_requirement}
</USER_REQUIREMENT>
"""


class _Scene(BaseModel):
    scene_id: int = Field(..., description="The scene number")
    heading: str = Field(..., description="The scene heading (e.g. INT. LOCATION - DAY)")
    action: str = Field(..., description="The action/description for the scene")


class _WriteScriptResponse(BaseModel):
    script: List[_Scene] = Field(
        ...,
        description="The script based on the story. Each element is a scene with scene_id, heading, and action.",
    )


class ScriptWriter:
    """Turn a story into a list of per-scene scripts."""

    def __init__(self, chat_model) -> None:
        self.chat_model = chat_model

    async def __call__(
        self,
        story: str,
        user_requirement: Optional[str] = None,
    ) -> List[str]:
        parser = PydanticOutputParser(pydantic_object=_WriteScriptResponse)
        format_instructions = parser.get_format_instructions()

        messages = [
            ("system", system_prompt_template_write_script.format(format_instructions=format_instructions)),
            ("human", human_prompt_template_write_script.format(story=story, user_requirement=user_requirement)),
        ]
        response = await self.chat_model.ainvoke(messages)
        response = parser.parse(response.content)
        return [f"{s.heading}\n\n{s.action}" for s in response.script]
