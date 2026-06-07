"""SceneExtractor — adapt a single novel event into a screenplay scene.

RAG-driven: receives context chunks retrieved from the source novel and
a sequence of previously-adapted scenes, and emits a :class:`Scene` with
environment, characters, and script.

The agent is constructed with a pre-initialized chat model and exposes
a single async method, :meth:`get_next_scene`.
"""

from __future__ import annotations

from typing import List

from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser

from schemas import Event, Scene
from utils.throttling import api_retry


system_prompt_template_extract_scene = \
"""
[Role]
You are a screenplay adapter. You turn a single literary event into a structured screenplay scene.

[Goal]
Given an event, retrieved context fragments, and prior scenes, emit the next scene — environment, characters, script.

[Input]
- An event description, enclosed in <EVENT_DESCRIPTION_START> / <EVENT_DESCRIPTION_END>.
- RAG context fragments, enclosed in <CONTEXT_FRAGMENTS_START> / <CONTEXT_FRAGMENTS_START>. Each fragment is wrapped in <FRAGMENT_N_START> / <FRAGMENT_N_END>.
- Previously adapted scenes (may be empty), enclosed in <PREVIOUS_SCENES_START> / <PREVIOUS_SCENES_END>. Each scene is wrapped in <SCENE_N_START> / <SCENE_N_END>.

[Output]
{format_instructions}

[Rules]
1. Ground every scene in the supplied context fragments. Drop fragments that don't bear on the event.
2. Convert descriptive prose into cinematic action and dialogue.
3. Each character is an individual, not a group.
4. Start a new scene whenever time or location changes. Cap the total at 5 scenes.
5. If the event lacks a detail, infer it logically from the event or wider context. Do not invent unrelated material.
6. Brief, visual descriptions. No camera jargon, no metaphors.
7. Language of all output values must match the input.
"""


human_prompt_template_extract_scene = \
"""
<EVENT_DESCRIPTION_START>
{event_description}
<EVENT_DESCRIPTION_END>

<CONTEXT_FRAGMENTS_START>
{context_fragments}
<CONTEXT_FRAGMENTS_END>

<PREVIOUS_SCENES_START>
{previous_scenes}
<PREVIOUS_SCENES_END>
"""


class SceneExtractor:
    """Adapt a single novel event into a screenplay scene (RAG-driven)."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    @api_retry(stop=5, reraise=False)
    async def get_next_scene(
        self,
        relevant_chunks: List[str],
        event: Event,
        previous_scenes: List[Scene],
    ) -> Scene:
        context_fragments_str = "\n".join(
            f"<FRAGMENT_{i}_START>\n{chunk}\n<FRAGMENT_{i}_END>"
            for i, chunk in enumerate(relevant_chunks)
        )
        previous_scenes_str = "\n".join(
            f"<SCENE_{i}_START>\n{scene}\n<SCENE_{i}_END>"
            for i, scene in enumerate(previous_scenes)
        )

        parser = PydanticOutputParser(pydantic_object=Scene)
        messages = [
            SystemMessage(content=system_prompt_template_extract_scene.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(content=human_prompt_template_extract_scene.format(
                event_description=str(event),
                context_fragments=context_fragments_str,
                previous_scenes=previous_scenes_str,
            )),
        ]

        chain = self.chat_model | parser
        scene = await chain.ainvoke(messages)
        return scene
