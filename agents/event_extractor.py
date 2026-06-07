"""EventExtractor — segment a novel into a chain of :class:`Event` records.

Walks the novel text one event at a time, each event capturing a
self-contained dramatic unit.  The chain ends when the LLM emits an
event with ``is_last=True``.

The agent is constructed with a pre-initialized chat model and exposes
a callable interface; the instance itself is invoked as a function and
its single public method is :meth:`extract_next_event`.
"""

from __future__ import annotations

import logging
from typing import List

from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser

from schemas import Event
from utils.throttling import api_retry


system_prompt_template_extract_event = \
"""
[Role]
You are a narrative-structure analyst. You segment a novel into a chain of dramatic events.

[Goal]
Emit the next event in sequence, building on the events already extracted.

[Input]
- The full novel text, enclosed in <NOVEL_TEXT_START> / <NOVEL_TEXT_END>.
- A list of events already extracted (may be empty), enclosed in <EXTRACTED_EVENTS_START> / <EXTRACTED_EVENTS_END>.

[Output]
{format_instructions}

[Rules]
1. Focus on events that drive plot, character development, or thematic weight.
2. Each event must be logically distinct from its neighbors.
3. If a dramatic unit spans multiple scenes, unify them under one event with a single dramatic goal.
4. Describe only what the text states. Do not infer or add details.
5. The `process_chain` field is a step-by-step account of the event's progression.
6. Language of all output values must match the input.
"""


human_prompt_template_extract_event = \
"""
<NOVEL_TEXT_START>
{novel_text}
<NOVEL_TEXT_END>

<EXTRACTED_EVENTS_START>
{extracted_events}
<EXTRACTED_EVENTS_END>
"""


class EventExtractor:
    """Segment a novel into a sequence of :class:`Event` records."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self.chat_model = chat_model
        self.parser = PydanticOutputParser(pydantic_object=Event)

    def __call__(self, novel_text: str) -> List[Event]:
        logging.info("Extracting events from novel...")
        events: List[Event] = []
        while True:
            event = self.extract_next_event(novel_text, events)
            events.append(event)
            logging.info(f"Extracted event: \n{event}")
            if event.is_last:
                break
        return events

    @api_retry(reraise=False)
    def extract_next_event(
        self,
        novel_text: str,
        extracted_events: List[Event],
    ) -> Event:
        extracted_events_str = "\n\n".join(str(e) for e in extracted_events)
        messages = [
            SystemMessage(content=system_prompt_template_extract_event.format(
                format_instructions=self.parser.get_format_instructions(),
            )),
            HumanMessage(content=human_prompt_template_extract_event.format(
                novel_text=novel_text,
                extracted_events=extracted_events_str,
            )),
        ]

        chain = self.chat_model | self.parser
        event: Event = chain.invoke(messages)
        assert event.index == len(extracted_events), (
            f"Extracted event index {event.index} does not match "
            f"the expected index {len(extracted_events)}"
        )
        return event
