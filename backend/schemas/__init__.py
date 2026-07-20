from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, TypedDict


class FrameRecord(TypedDict):
    """A single per-shot asset produced during the frame pipeline."""
    shot_idx: int
    frame_type: str
    path: str
    url: str


class ReferenceSelection(BaseModel):
    selected_indices: List[int] = Field(
        description='从提供的参考图像列表中选取的图像索引，索引从0开始。例如 [0, 2, 5] 表示选用第1、第3和第6张图像。',
        examples=[[1, 3]],
    )
    generation_prompt: str = Field(
        description='指导图像生成的文本提示。需明确描述待生成画面的具体内容，并注明画面中哪些元素应参照哪一张被选用的参考图（及其局部元素）。参照格式必须使用"Image N"，其中 N 为 selected_indices 列表中的位置索引（而非原始图像列表的绝对序号）。',
        examples=[
            '根据以下指引生成图像：\n该男子站立在风景中。男子的外观参照 Image 0。风景参照 Image 1。',
        ],
    )


class CreateProject(BaseModel):
    name: str
    language: str = "zh"


class GenerateRequest(BaseModel):
    prompt: str
    model: str
    api_key: str = ""
    base_url: str = ""
    system_prompt: str = ""


class StoryRequest(BaseModel):
    idea: str
    model: str
    api_key: str = ""
    base_url: str = ""
    user_requirement: str = ""


class CharacterRequest(BaseModel):
    script: str
    model: str
    api_key: str = ""
    base_url: str = ""


class ScriptRequest(BaseModel):
    story: str
    characters_text: str = ""
    model: str
    api_key: str = ""
    base_url: str = ""
    user_requirement: str = ""


class SceneStoryboardRequest(BaseModel):
    project_id: int = 0
    scene_idx: int = 0
    scene_content: str
    characters: List[dict] = []
    user_requirement: str = ""
    style: str = ""
    model: str
    api_key: str = ""
    base_url: str = ""


class SceneStoryboardBatchItem(BaseModel):
    scene_content: str
    user_requirement: str = ""


class SceneStoryboardBatchRequest(BaseModel):
    scenes: List[SceneStoryboardBatchItem]
    characters: List[dict] = []
    style: str = ""
    model: str
    api_key: str = ""
    base_url: str = ""


from backend.schemas.character import CharacterRead, CharacterSave, PortraitCharacter


class PortraitRequest(BaseModel):
    characters: List[PortraitCharacter]
    view: str = "front"
    style: str = ""
    model: str
    api_key: str = ""
    base_url: str = ""
    size: Optional[str] = None
    project_id: int


class ShotSave(BaseModel):
    title: str = ""
    visual_description: str = Field(default="", alias="visualDescription")
    voice_description: str = Field(default="", alias="voiceDescription")
    motion_description: str = Field(default="", alias="motionDescription")
    variation_type: str = Field(default="medium", alias="variationType")
    first_frame: str = Field(default="", alias="firstFrame")
    last_frame: str = Field(default="", alias="lastFrame")
    video: str = ""
    video_preview: str = Field(default="", alias="videoPreview")


class SceneSave(BaseModel):
    title: str = ""
    content: str = ""
    slugline: str = ""
    environment_desc: str = Field(default="", alias="environmentDesc")
    script: str = ""
    composited_video: str = Field(default="", alias="compositedVideo")
    composited_preview: str = Field(default="", alias="compositedPreview")
    shots: List[ShotSave] = []


class GenerateFrameRequest(BaseModel):
    prompt: str
    size: str = "1024x576"
    model: str
    api_key: str = ""
    base_url: str = ""
    reference_images: List[str] = []


class GenerateShotFramesRequest(BaseModel):
    camera_tree: List[dict]
    shot_descriptions: List[dict]
    characters: List[dict]
    character_portraits_registry: dict = {}
    model: str
    chat_model: str = ""
    api_key: str = ""
    base_url: str = ""
    project_id: int = 0
    size: str = "1024x576"
    scene_idx: int = 0


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    idea: Optional[str] = None
    style: Optional[str] = None
    size: Optional[str] = None
    size_tier: Optional[str] = None
    resolution: Optional[str] = None
    frame_rate: Optional[int] = None
    duration: Optional[int] = None
    chat_model: Optional[str] = None
    chat_base_url: Optional[str] = None
    image_model: Optional[str] = None
    image_base_url: Optional[str] = None
    video_model: Optional[str] = None
    video_base_url: Optional[str] = None
    stage: Optional[str] = None
    story: Optional[str] = None
    storyTitle: Optional[str] = None
    characters: Optional[List[CharacterSave]] = None
    scenes: Optional[List[SceneSave]] = None
    final_video: Optional[str] = Field(default=None, alias="finalVideo")
    final_preview: Optional[str] = Field(default=None, alias="finalPreview")


class RegenerateStepRequest(BaseModel):
    step: str
    chat_api_key: str = ""
    chat_base_url: str = ""
    image_api_key: str = ""
    image_base_url: str = ""
    video_api_key: str = ""
    video_base_url: str = ""


class PipelineStartRequest(BaseModel):
    start_step: Optional[str] = None
    chat_api_key: str = ""
    chat_base_url: str = ""
    image_api_key: str = ""
    image_base_url: str = ""
    video_api_key: str = ""
    video_base_url: str = ""
    chat_rate_limit_min: int = 50
    chat_rate_limit_day: int = 2000
    image_rate_limit_min: int = 10
    image_rate_limit_day: int = 500
    video_rate_limit_min: int = 1
    video_rate_limit_day: int = 1000


class StoryOutput(BaseModel):
    title: str = Field(
        description="""剧名/片名，抓人眼球且契合故事内核的暂定名。例如"我的影子朋友"、 "星际迷航"等。""",
    )
    content: str = Field(
        description="""完整的影视故事策划文档正文（不含剧名），需包含以下模块（纯文本格式）：
- 受众画像与题材类型：开篇需明确定调
- 核心梗概：100-200字高度凝练的故事梗概
- 主要人物：核心角色介绍
- 完整故事大纲：按剧作结构展开的完整故事""",
    )


class StoryUpdate(BaseModel):
    content: str


class PortraitsUpdate(BaseModel):
    portraits: dict  # {identifier: {front: url, side: url, back: url}}


class SceneScriptsUpdate(BaseModel):
    scenes: List[Dict[str, Any]]


class StoryboardUpdate(BaseModel):
    scenes: List[Dict[str, Any]]


class ShotFramesUpdate(BaseModel):
    shots: List[dict]


class RateLimitUpdate(BaseModel):
    model: str
    rpm: int
    rpd: int


class RateLimitDefaults(BaseModel):
    """应用启动时批量设置各模型的默认限流值。"""
    defaults: Dict[str, tuple[int, int]]  # {model_name: (rpm, rpd)}
