"""Camera tree node for the Clipsay storyboard graph.

A scene's shot list is broken into *cameras* — each camera is a stable
viewpoint that films one or more consecutive shots.  A non-root camera
inherits whatever visual context it can from its parent's frame so that
the i2v animation doesn't have to hallucinate the background.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class CameraSetup(BaseModel):
    """A single node in the scene's camera tree."""

    idx: int = Field(
        description="The index of the camera in the scene, starting from 0.",
        examples=[0, 1, 2],
    )

    active_shot_idxs: List[int] = Field(
        description="The indices of the shots that this camera can film.",
        examples=[[0, 1], [2, 3, 4], [5]],
    )

    parent_cam_idx: Optional[int] = Field(
        default=None,
        description="The index of the parent camera, or None for a root camera.",
    )

    parent_shot_idx: Optional[int] = Field(
        default=None,
        description="The index of the parent's last frame used as the i2v anchor, "
                    "or None for a root camera.",
    )

    reason: Optional[str] = Field(
        default=None,
        description="The reason for selecting this parent camera, or None for a root camera.",
    )

    is_parent_fully_covers_child: Optional[bool] = Field(
        default=None,
        description="Whether the parent camera's last frame fully covers the first "
                    "frame of the first child shot. None for a root camera.",
    )

    missing_info: Optional[str] = Field(
        default=None,
        description="The visual context the parent frame doesn't cover and that the "
                    "child shot must regenerate, or None if coverage is complete.",
    )
