"""A single frame at a specific point in a shot."""

from pydantic import BaseModel, Field
from typing import List, Literal


class Frame(BaseModel):
    """A single frame at a specific point in a shot."""

    shot_idx: int = Field(
        description="The index of the shot in the sequence, starting from 0.",
        examples=[0, 1, 2],
    )

    frame_type: Literal["first", "last"] = Field(
        description="Whether this is the first or last frame of the shot.",
        examples=["first", "last"],
    )

    cam_idx: int = Field(
        description="The index of the camera used for this frame, starting from 0.",
        examples=[0, 1, 2],
    )

    vis_char_idxs: List[int] = Field(
        description="Indices of characters that are visible in this frame, into the "
                    "character list of the parent scene.",
        examples=[[0, 1], [0], []],
    )
