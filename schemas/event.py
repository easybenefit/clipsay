"""A single event in the story's causal chain.

An :class:`Event` is the unit of plot.  It is captured in two pieces:
a one-sentence description for the story outline, and a process chain
of ordered steps that drive the scene-level storyboard.
"""

from pydantic import BaseModel, Field
from typing import List


class Event(BaseModel):
    """A single event in the story's causal chain."""

    idx: int = Field(
        description="The index of the event in the sequence, starting from 0.",
        examples=[0, 1, 2],
    )

    is_last: bool = Field(
        description="Whether this is the last event in the sequence.",
        examples=[False, True],
    )

    description: str = Field(
        description="A one-sentence summary of the event, capturing its essence.",
        examples=[
            "A thief who stole a gem from a museum was caught after a rooftop chase "
            "with guards, and the gem was recovered.",
        ],
    )

    process_chain: List[str] = Field(
        description="An ordered list of steps that make up the event's complete "
                    "causal chain. Each step should be a self-contained sentence.",
        examples=[
            [
                "A thief steals a gem from a museum, triggering the alarm. Guards notice and begin the chase.",
                "The thief rushes out the museum's back door and dashes through narrow alleys, with guards closely pursuing and calling for backup.",
                "The thief climbs a fire escape to the rooftops; the guards follow using low platforms on adjacent buildings.",
                "The thief leaps across a 1.5-meter gap between two buildings. The guards hesitate but take the risky jump, nearly losing their footing.",
                "The thief knocks over stacked wooden planks to create an obstacle. The guards dodge but lose speed.",
                "The thief attempts to slide down a rope to the opposite rooftop, but a guard lunges and grabs their ankle. Both tumble and grapple.",
                "Backup arrives, subduing the thief and recovering the gem.",
            ],
        ],
    )

    def __str__(self) -> str:
        lines = [
            f"<Event {self.idx}>",
            f"Description: {self.description}",
            "Process Chain:",
        ]
        lines.extend(f"- {step}" for step in self.process_chain)
        return "\n".join(lines)
