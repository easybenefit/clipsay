"""CharacterExtractor — pull the cast and visual features from a script.

The agent reads a screenplay script and emits a deduplicated list of
every speaking or visually present character with the static and
dynamic features the renderer needs to keep them consistent across
shots.

The agent is constructed with a pre-initialized chat model and
exposes a single async method, :meth:`extract_characters`.
"""

from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from schemas import CharacterInScene
from utils.throttling import api_retry


system_prompt_template_extract_characters = \
"""
[Role]
You are a script analyst. You extract the cast from a script so a downstream video pipeline can render every speaking or visible character.

[Goal]
Produce a deduplicated list of characters with visual features precise enough for image generation.

[Input]
- A script enclosed in <SCRIPT> / </SCRIPT>.

[Output]
{format_instructions}

[Rules]
1. Language of all output values must match the script.
2. Merge every reference to the same entity under one character. Use the most natural identifier; keep real famous names as-is (e.g., "Elon Musk", "Bill Gates").
3. For unnamed characters, use a stable descriptor (e.g., "the barista", "the young woman in the red coat").
4. Skip extras with no narrative presence.
5. If the script only partially describes a character, fill in plausible physical features from context. Concrete, visual, specific — no abstract adjectives like "beautiful" or "mysterious".
6. Split each character's features into:
   - static — physical appearance and physique (unchanging).
   - dynamic — outfit, accessories, and carried items (changeable per scene).
7. Never include personality, role, or relationship text in either feature bucket.
"""


human_prompt_template_extract_characters = \
"""
<SCRIPT>
{script}
</SCRIPT>
"""


class ExtractCharactersResponse(BaseModel):
    characters: List[CharacterInScene] = Field(
        ..., description="A list of characters extracted from the script."
    )


class CharacterExtractor:
    def __init__(self, chat_model) -> None:
        self.chat_model = chat_model

    @api_retry(reraise=False)
    async def extract_characters(self, script: str) -> List[CharacterInScene]:
        parser = PydanticOutputParser(pydantic_object=ExtractCharactersResponse)

        messages = [
            SystemMessage(content=system_prompt_template_extract_characters.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(content=human_prompt_template_extract_characters.format(script=script)),
        ]

        chain = self.chat_model | parser
        response: ExtractCharactersResponse = await chain.ainvoke(messages)
        return response.characters
