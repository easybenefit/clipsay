"""StoryDeveloper — expand a one-line idea into a structured story.

Takes a short idea (a sentence, a concept, a setting, or a scene)
plus optional user requirements and produces a complete story
document that downstream stages (character extraction, script writing)
can consume.

The agent is constructed with a pre-initialized chat model and
exposes an async callable interface — the instance itself is invoked
as a function.  It performs a single, well-defined step in the
Clipsay pipeline.
"""

from __future__ import annotations

from typing import Optional


system_prompt_template_develop_story = \
"""
[Role]
You are a story developer. You turn a one-line idea into a filmable story document.

[Goal]
Produce a structured story that downstream stages can break into scenes and shots.

[Input]
- An idea, enclosed in <IDEA> / </IDEA>. A single sentence, a concept, a setting, or a scene.
- An optional user requirement, enclosed in <USER_REQUIREMENT> / </USER_REQUIREMENT>. May include target audience, genre, length, or specific notes.

[Output]
A story document with these sections, in this order:
1. **Story Title** — engaging, on-theme.
2. **Audience & Genre** — restate explicitly: "This story is targeted at <audience>, in the <genre> genre."
3. **Outline** — 100-200 words. Core plot, central conflict, outcome.
4. **Main Characters** — name, key traits, motivation.
5. **Full Story Narrative** — vivid, concrete, matches genre and audience. If a scene count was specified, divide into exactly that many scenes with subheadings. Otherwise, follow Introduction → Development → Climax → Conclusion.
6. End the output with the story. No trailing commentary.

[Rules]
1. Language of all output values must match the input idea.
2. Stay idea-centric. Expand, do not deviate.
3. Event progression and character behavior must be logically consistent. No contradictions.
4. Show, don't tell. "He clenched his fist, nails digging into his palm" beats "He was angry".
5. Concrete, visual descriptions. Vary sentence rhythm.
6. Original, positive, safe content.
"""


human_prompt_template_develop_story = \
"""
<IDEA>
{idea}
</IDEA>

<USER_REQUIREMENT>
{user_requirement}
</USER_REQUIREMENT>
"""


class StoryDeveloper:
    """Expand a one-line idea into a structured story."""

    def __init__(self, chat_model) -> None:
        self.chat_model = chat_model

    async def __call__(
        self,
        idea: str,
        user_requirement: Optional[str] = None,
    ) -> str:
        messages = [
            ("system", system_prompt_template_develop_story),
            ("human", human_prompt_template_develop_story.format(
                idea=idea, user_requirement=user_requirement,
            )),
        ]
        response = await self.chat_model.ainvoke(messages)
        return response.content
