from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SceneCharacter(BaseModel):
    idx: int = Field(description="角色在场景中的索引，从0开始")
    identifier: str = Field(description="该角色在当前场景中的标识符（如称呼、代号）")
    visible: bool = Field(description="该角色在当前场景中是否可见")
    appearance: str = Field(description="静态特征：外貌、体型等相对不变的生理描述")
    attire: str = Field(description="动态特征：服装、配饰、关键道具等易变的造型描述")


class CharactersResponse(BaseModel):
    characters: List[SceneCharacter] = Field(description="从剧本中提取的角色列表")


class CharacterSave(BaseModel):
    identifier: str
    appearance: str = Field(default="", alias="staticFeatures")
    attire: str = Field(default="", alias="dynamicFeatures")
    source: str = "script"
    portraits: dict = {}
    source_url: str = Field(default="", alias="sourceUrl")
    visible: bool = True
    idx: int = 0


class CharacterRead(BaseModel):
    identifier: str
    appearance: str = ""
    attire: str = ""
    front_path: str = ""
    side_path: str = ""
    back_path: str = ""
    front_url: str = ""
    side_url: str = ""
    back_url: str = ""
    char_idx: int = 0


class PortraitCharacter(BaseModel):
    identifier: str
    appearance: str = ""
    attire: str = ""
    front_image: Optional[str] = None
