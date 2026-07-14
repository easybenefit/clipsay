"""Script schema models for LLM output parsing."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ScriptScene(BaseModel):
    scene_id: int = Field(..., description="场次编号")
    heading: str = Field(..., description="场景标题（如：内. 地点 - 白天）")
    action: str = Field(..., description="该场景的动作/描述")


class ScriptSceneList(BaseModel):
    script: List[ScriptScene] = Field(
        ...,
        description="根据故事生成的剧本。每个元素为一个场景，包含场次编号、场景标题及动作/描述。",
    )