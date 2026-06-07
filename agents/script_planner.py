"""ScriptPlanner — turn a one-line idea into a fully-planned script.

Routes the idea to one of three planning templates (narrative, motion,
montage) and runs the matching prompt through a chat model.  The
result is a long-form, cinematic script ready for downstream
storyboarding.

The agent is constructed with a pre-initialized chat model (typically
the same one used for the rest of the pipeline) and exposes a single
sync method, :meth:`plan_script`.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from langchain.chat_models.base import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from utils.throttling import api_retry


system_prompt_template_route_intent = \
"""
[Role]
You classify ideas for the script planner.

[Goal]
Pick exactly one of: narrative, motion, montage.

[Input]
- A basic idea, enclosed in <BASIC_IDEA_START> / <BASIC_IDEA_END>.

[Output]
{format_instructions}

[Rules]
- **narrative** — character, plot, themes, dialogue, or broad storytelling beats.
- **motion** — action, speed, vehicles, combat, choreography, sports, or any kinetic sequence where precise technical motion is primary.
- **montage** — a sequence of shots that conveys an emotional arc through imagery, pacing, and juxtaposition.
"""


human_prompt_template_plan_script = \
"""
<BASIC_IDEA_START>
{basic_idea}
<BASIC_IDEA_END>
"""


system_prompt_template_plan_narrative = \
"""
[Role]
You are a screenplay writer. You turn a one-line idea into a cinematic script with clear three-act structure and character arcs.

[Goal]
Plan a script with rich narrative detail and a setup → confrontation → resolution shape.

[Input]
- A basic story idea, enclosed in <BASIC_IDEA_START> / <BASIC_IDEA_END>.

[Output]
{format_instructions}

[Rules]
1. Three-act structure: setup, confrontation, resolution. Advance the plot, do not summarize it.
2. Characters with clear motivations, flaws, and arcs.
3. Cinematic writing: actions, atmosphere, visual detail.
4. Pace for tension. Use scene transitions, conflict escalation, and strategic revelation.
5. Match tone, style, and conventions to the genre.
6. Spoken lines use :"dialogue" form. No voiceover.
7. Establish clear external and internal conflicts with high stakes.
8. Resolve all major plot threads.
9. No metaphors. No camera directions.
"""


system_prompt_template_plan_motion = \
"""
[Role]
You are an action and motion-sequence script designer. You write technically accurate kinetic scenes.

[Goal]
Turn a one-line idea into a motion-driven script with precise action beats ready for storyboarding.

[Input]
- A basic idea, enclosed in <BASIC_IDEA_START> / <BASIC_IDEA_END>.

[Output]
{format_instructions}

[Rules]
1. Precise nouns and qualifiers. Trajectories, vectors, speed, force — make them explicit.
2. Maintain a consistent spatial map. The reader must never lose track of who is where.
3. Step-by-step beats that can be storyboarded one-for-one.
4. Spoken lines use :"dialogue" form. Keep dialogue sparse.
5. Favor exterior shots over character close-ups.
6. Allow at most one character unless the user specifies more.
7. Do not describe a character's physical appearance. The renderer handles that.
8. No metaphors. No camera directions.
"""


system_prompt_template_plan_montage = \
"""
[Role]
You are a montage script designer. You compress time and shape emotional arcs through shot selection, rhythm, and juxtaposition.

[Goal]
Turn a one-line idea into an emotion-driven montage script with clear per-beat progression.

[Input]
- A basic idea, enclosed in <BASIC_IDEA_START> / <BASIC_IDEA_END>.

[Output]
{format_instructions}

[Rules]
1. Pure paragraphs. No dialogue unless it marks a clear emotional shift (use :"dialogue" form).
2. Multiple shots per scene to drive the montage rhythm.
3. Total length: at least 500 words. Each paragraph: at most 50 words.
4. Build a clear emotional arc. State the change in emotional state and its cause in each beat.
5. Sparse, precise notes for sound and music. No elaborate score direction.
6. Limit complex external action. Focus on expressive visuals.
7. Describe only physical traits that influence or reveal emotion.
8. No metaphors. No poetic language. No camera directions.
"""


class IntentRouterResponse(BaseModel):
    intent: Literal["narrative", "motion", "montage"] = Field(
        ...,
        description="Routing decision: 'narrative' for character/plot focus, "
                    "'motion' for action/kinetic focus, 'montage' for emotional montage.",
    )
    rationale: Optional[str] = Field(
        default=None, description="Brief reason for the classification.",
    )


class PlannedScriptResponse(BaseModel):
    planned_script: str = Field(
        ...,
        description="The full planned script with rich narrative detail, character "
                    "development, dialogue, and cinematic descriptions.",
    )


class ScriptPlanner:
    """Plan a comprehensive script from a basic idea."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model

    def _select_template(self, intent: str) -> str:
        return {
            "narrative": system_prompt_template_plan_narrative,
            "motion": system_prompt_template_plan_motion,
            "montage": system_prompt_template_plan_montage,
        }.get(intent, system_prompt_template_plan_narrative)

    @api_retry(reraise=False)
    def plan_script(self, basic_idea: str) -> PlannedScriptResponse:
        """Plan a comprehensive script from a basic idea.

        Returns a :class:`PlannedScriptResponse` whose ``planned_script`` is
        a long-form, cinematic script ready for downstream storyboarding.
        """
        # 1) Route intent.
        router_parser = PydanticOutputParser(pydantic_object=IntentRouterResponse)
        router_messages = [
            ("system", system_prompt_template_route_intent.format(
                format_instructions=router_parser.get_format_instructions(),
            )),
            ("human", human_prompt_template_plan_script.format(basic_idea=basic_idea)),
        ]
        try:
            routing = self.chat_model.invoke(router_messages)
            chosen_intent = (
                routing.intent
                if isinstance(routing, IntentRouterResponse)
                else "narrative"
            )
        except Exception:
            chosen_intent = "narrative"
        logging.info(f"[ScriptPlanner] Intent routed to: {chosen_intent}")

        # 2) Run the planning chain with the selected template.
        planning_parser = PydanticOutputParser(pydantic_object=PlannedScriptResponse)
        system_template = self._select_template(chosen_intent).format(
            format_instructions=planning_parser.get_format_instructions(),
        )
        planning_messages = [
            ("system", system_template),
            ("human", human_prompt_template_plan_script.format(basic_idea=basic_idea)),
        ]
        try:
            response = self.chat_model.invoke(planning_messages)
            if isinstance(response, PlannedScriptResponse):
                return response
            return planning_parser.parse(response.content)
        except Exception as e:
            logging.error(f"Error planning script: \n{e}")
            raise
