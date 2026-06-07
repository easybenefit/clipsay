"""Character records at three levels of granularity.

* :class:`CharacterInScene` — the most concrete.  Carries the dynamic
  features (clothing, accessories) the character wears in a specific
  scene, used by the renderer to keep the look consistent.
* :class:`CharacterInEvent` — the bridge between the novel and the
  scene.  Tracks which scenes the character is active in and which
  identifier the scene uses for them.
* :class:`CharacterInNovel` — the top-level.  Static physical features
  shared across every event and scene the character appears in.

All three share the same static-feature text so the portrait generator
can pull a single source of truth for "what does Alice look like".
"""

from pydantic import BaseModel, Field
from typing import Dict


class CharacterInScene(BaseModel):
    """A character's appearance within a single scene."""

    idx: int = Field(
        description="The index of the character in the scene, starting from 0.",
        examples=[0, 1, 2],
    )
    identifier_in_scene: str = Field(
        description="The identifier used for the character in this scene. May differ "
                    "from the base identifier if the role changes (e.g. 'Young Alice').",
        examples=["Alice", "Bob the Builder"],
    )
    is_visible: bool = Field(
        description="Whether the character appears on screen in this scene.",
        examples=[True, False],
    )
    static_features: str = Field(
        description="Physical features that rarely change (face, build). Empty if the "
                    "character is not visible in this scene.",
        examples=[
            "Alice has long blonde hair and blue eyes, and is of slender build.",
            "Bob the Builder is a middle-aged man with a sturdy build.",
        ],
    )
    dynamic_features: str = Field(
        description="Per-scene features such as clothing and accessories. Empty if the "
                    "character is not visible.",
        examples=["Wearing a red scarf and a black leather jacket."],
    )

    def __str__(self) -> str:
        visibility = "[visible]" if self.is_visible else "[not visible]"
        return (
            f"{self.identifier_in_scene}{visibility}\n"
            f"static features: {self.static_features}\n"
            f"dynamic features: {self.dynamic_features}\n"
        )


class CharacterInEvent(BaseModel):
    """A character's reach across the scenes of a single event."""

    idx: int = Field(
        description="The index of the character in the event, starting from 0.",
        examples=[0, 1],
    )
    identifier_in_event: str = Field(
        description="The unique identifier for the character in this event.",
        examples=["Alice", "Bob the Builder"],
    )
    active_scenes: Dict[int, str] = Field(
        description="Mapping of scene index -> the identifier the character uses in that scene.",
        examples=[
            {0: "Alice", 2: "Alice in Wonderland", 5: "Alice"},
            {1: "Bob the Builder", 3: "Bob", 4: "Bob"},
        ],
    )
    static_features: str = Field(
        description="Physical features that rarely change across scenes.",
        examples=[
            "Alice has long blonde hair and blue eyes, and is of slender build. "
            "She often wears casual, comfortable clothing.",
        ],
    )


class CharacterInNovel(BaseModel):
    """A character's reach across the events of a single novel."""

    idx: int = Field(
        description="The index of the character in the novel, starting from 0.",
        examples=[0, 1],
    )
    identifier_in_novel: str = Field(
        description="The unique identifier for the character in the novel.",
        examples=["Alice", "Bob the Builder"],
    )
    active_events: Dict[int, str] = Field(
        description="Mapping of event index -> the identifier the character uses in that event.",
        examples=[
            {0: "Alice", 2: "Alice in Wonderland", 5: "Alice"},
            {1: "Bob the Builder", 3: "Bob", 4: "Bob"},
        ],
    )
    static_features: str = Field(
        description="Physical features that rarely change across the entire novel.",
        examples=[
            "Alice has long blonde hair and blue eyes, and is of slender build. "
            "She often wears casual, comfortable clothing.",
        ],
    )
