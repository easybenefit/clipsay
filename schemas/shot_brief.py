"""Concise description of a single shot in the storyboard.

A :class:`ShotBrief` is what the script planner hands the
:class:`agents.StoryboardArtist` for one shot: position in the
sequence, the camera that films it, the visual content, and the audio
content.  The storyboard artist expands this into a :class:`ShotSpec`
once the per-shot frame decomposition is known.
"""

from pydantic import BaseModel, Field


class ShotBrief(BaseModel):
    """A concise description of a single shot."""

    idx: int = Field(
        description="The index of the shot in the sequence, starting from 0.",
        examples=[0, 1, 2],
    )
    is_last: bool = Field(
        description="Whether this is the last shot. If true, the story has ended and "
                    "no more shots will be planned after this one.",
        examples=[False, True],
    )

    cam_idx: int = Field(
        description="The index of the camera in the scene.",
        examples=[0, 1, 2],
    )

    visual_desc: str = Field(
        description="A vivid and detailed visual description of the shot. The character "
                    "identifiers in the description must match those in the character "
                    "list and be enclosed in angle brackets (e.g. <Alice>, <Bob>). All "
                    "visible characters should be described. Dialogue, if any, should be "
                    "written into the visual content with \"\" symbols and the speaker's "
                    "features, e.g. <SLING> (male, late 20s, Texan accent softened by "
                    "military precision, confident and energetic.) says: \"Gear retracted. "
                    "Flaps transitioning. Flight path stable. You are clear to climb.\"",
        examples=[
            "An over-the-shoulder shot at eye level, positioned behind <Alice>. The "
            "foreground, including <Alice>'s shoulder and head, is softly blurred, "
            "directing focus onto <Bob>'s face. <Bob>'s subtle reactions—shifting from "
            "surprise to delight—are clearly visible. The supermarket background is "
            "gently blurred with cool fluorescent lighting.",
        ],
    )

    audio_desc: str = Field(
        description="A detailed description of the audio in the shot.",
        examples=[
            "[Sound Effect] Ambient sound (supermarket background noise, shopping cart wheels rolling)",
            "[Speaker] Alice (Happy): Hello, how are you?",
            "",
        ],
    )

    def __str__(self) -> str:
        lines = [
            f"Shot {self.idx}:",
            f"Camera Index: {self.cam_idx}",
            f"Visual: {self.visual_desc}",
        ]
        if self.audio_desc:
            lines.append(f"Audio: {self.audio_desc}")
        return "\n".join(lines)
