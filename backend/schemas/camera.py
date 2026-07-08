from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CameraParentItem(BaseModel):
    parent_cam_idx: Optional[int] = Field(
        default=None,
        description="父摄影机的索引。若该摄影机为根摄影机（无父级），则设为 None。",
        examples=[0, 1],
    )
    parent_shot_idx: Optional[int] = Field(
        default=None,
        description="父镜头（即依赖的上一级镜头）的索引。若该摄影机为根摄影机，则设为 None。",
        examples=[0, 3],
    )
    reason: str = Field(
        description="选定此父摄影机的理由。若为根摄影机，需说明其为何是根摄影机。",
    )
    is_parent_fully_covers_child: Optional[bool] = Field(
        default=None,
        description="父摄影机是否在内容上完全覆盖子摄影机。若该摄影机无父级，则设为 None。",
    )
    missing_info: Optional[str] = Field(
        default=None,
        description="子镜头中未被父镜头覆盖的缺失元素。若父镜头已完全覆盖子镜头，则设为 None。",
    )


class CameraTreeResponse(BaseModel):
    camera_parent_items: List[Optional[CameraParentItem]] = Field(
        description="每台摄影机对应的父级关联信息。列表顺序与摄影机编号顺序一致。",
    )


class CameraNode(BaseModel):
    idx: int
    active_shot_idxs: List[int]
    parent_cam_idx: Optional[int] = None
    parent_shot_idx: Optional[int] = None
    reason: Optional[str] = None
    is_parent_fully_covers_child: Optional[bool] = None
    missing_info: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump()
