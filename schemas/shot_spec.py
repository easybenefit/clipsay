"""Fully-decomposed specification of a single shot.

A :class:`ShotSpec` is the expansion of a :class:`ShotBrief` once the
storyboard artist has decided how the shot animates.  It carries the
first and last frame descriptions, the motion between them, the audio
track, and a *variation type* that tells the renderer how much the
content changes from first frame to last frame.
"""

from pydantic import BaseModel, Field
from typing import List, Literal


class ShotSpec(BaseModel):
    """A fully-decomposed specification of a single shot."""

    idx: int = Field(
        description="The index of the shot in the sequence, starting from 0.",
        examples=[0, 1, 2],
    )
    is_last: bool = Field(
        description="Whether this is the last shot in the sequence. If true, no more "
                    "shots will be planned after this one.",
        examples=[False, True],
    )

    cam_idx: int = Field(
        description="The index of the camera in the scene.",
        examples=[0, 1, 2],
    )
    visual_desc: str = Field(
        description="A vivid and detailed visual description of the shot. Character "
                    "identifiers must match the character list and be enclosed in angle "
                    "brackets (e.g. <Alice>, <Bob>). Dialogue, if any, should be written "
                    "into the visual content with \"\" symbols and the speaker's features.",
        examples=[
            "An over-the-shoulder shot at eye level, positioned behind <Alice>. The "
            "foreground, including <Alice>'s shoulder and head, is softly blurred, "
            "directing focus onto <Bob>'s face. <Bob>'s subtle reactions—shifting from "
            "surprise to delight—are clearly visible. The supermarket background is "
            "gently blurred with cool fluorescent lighting.",
        ],
    )
    variation_type: Literal["large", "medium", "small"] = Field(
        description="How much the shot's content changes from first frame to last frame.",
        examples=["large", "medium", "small"],
    )
    variation_reason: str = Field(
        description="The reason for the variation type assignment.",
        examples=[
            "This is a transition shot where the first and last frame content differ "
            "dramatically, so the variation type is large.",
            "Compared to the first frame, a new character appears in the last frame, "
            "and there are no significant changes in the composition. The variation type "
            "is medium.",
            "Compared to the first frame, there are only minor changes in the "
            "composition. The variation type is small.",
            "This shot only shows Alice speaking and her facial expressions change, so "
            "the variation type is small.",
        ],
    )

    ff_desc: str = Field(
        description="The first frame of the shot.",
        examples=[
            "Medium shot of a supermarket aisle at eye level. Bob (a tall man wearing "
            "a blue shirt and jeans) is positioned on the right side of the frame, "
            "captured in profile and facing right, while Alice (a young woman with "
            "short hair, wearing a green dress) is on the left, shown pushing a "
            "shopping cart with her gaze lowered toward the ground. They are arranged "
            "in a front-to-back spatial relationship. Shelves line both sides of the "
            "frame, and cool-toned fluorescent lighting from above washes over the "
            "scene.",
        ],
    )
    ff_vis_char_idxs: List[int] = Field(
        default_factory=list,
        description="Indices of characters visible in the first frame, into the "
                    "parent scene's character list.",
        examples=[[0, 1], [0], []],
    )
    lf_desc: str = Field(
        description="The last frame of the shot.",
    )
    lf_vis_char_idxs: List[int] = Field(
        default_factory=list,
        description="Indices of characters visible in the last frame, into the "
                    "parent scene's character list.",
        examples=[[0, 1], [0], []],
    )
    motion_desc: str = Field(
        description="A description of the motion between the first and last frame. "
                    "Dialogue, if any, should be written into the motion description "
                    "with \"\" symbols and the speaker's features. Narration, if any, "
                    "should be written in the same form with the 'Narration:' label.",
    )

    audio_desc: str = Field(
        description="A detailed description of the audio in the shot.",
        examples=[
            "[Sound Effect] Ambient sound (supermarket background noise, shopping cart wheels rolling)",
            "[Speaker] Alice (Happy): Hello, how are you?",
            "",
        ],
    )
