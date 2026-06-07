"""Per-scene script record.

A :class:`Scene` binds the four pieces the storyboard needs:

* the environment in which it plays,
* the cast and their per-scene appearance,
* the screenplay script (with character actions and dialogue),
* its position in the overall sequence (``idx`` and ``is_last``).
"""

from pydantic import BaseModel, Field
from typing import List

from .characters import CharacterInScene
from .environment import EnvironmentInScene


class Scene(BaseModel):
    """A single scene in the screenplay."""

    idx: int = Field(
        description="The scene index, starting from 0.",
        examples=[0, 1, 2],
    )
    is_last: bool = Field(
        description="Whether this is the last scene in the sequence.",
        examples=[False, True],
    )
    environment: EnvironmentInScene = Field(
        description="The detailed scene setting, including location and time of day.",
    )
    characters: List[CharacterInScene] = Field(
        description="A list of characters appearing in the scene, along with their "
                    "dynamic features (clothing, accessories) for this scene.",
    )
    script: str = Field(
        description="The screenplay script for the scene — character actions and "
                    "dialogue. Character names in the script must be enclosed in <> "
                    "except for character names within dialogues.",
        examples=[
            "<Jane> paces nervously, clutching a letter. She turns to <John>.\n"
            "<Jane>: John, we need to leave tonight.\n"
            "<John> shakes his head, stepping toward the window.\n"
            "<John>: It's too dangerous.",

            "<Alice> sits quietly, observing the chaos around her. She whispers to <Bob>.\n"
            "<Alice>: Bob, do you think they'll find us here?\n"
            "<Bob> nods slowly, his expression grim.",
        ],
    )

    def __str__(self) -> str:
        cast = ", ".join(str(c) for c in self.characters)
        return (
            f"Scene {self.idx}:\n"
            f"Environment: {self.environment}\n"
            f"Characters: {cast}\n"
            f"Script: \n{self.script}"
        )
