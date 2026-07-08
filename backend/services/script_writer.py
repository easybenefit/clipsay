from __future__ import annotations

from typing import List, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from backend.clients.llm import LLM
from backend.utils.logging import setup_logger

logger = setup_logger("script_writer")


SYSTEM_PROMPT_WRITE_SCRIPT = \
"""
[角色]
你是一名专业的影视工业剧本改编专家，精通从文学故事到影视剧本（电影、长剧、微短剧）的高品质转化。你具备以下核心能力：
- 故事拆解能力：能深度理解故事内容，精准识别关键情节点、人物弧光与主题表达。
- 分场设计能力：能依据时间与空间的连续逻辑，将故事拆分为合理的场景单元，形成具有节奏感的场景序列。
- 剧本执行能力：深谙影视工业通用剧本格式（如电影剧本、剧集剧本、微短剧速读剧本），能生成生动的对白、行为描写和舞台指示。
- 需求适配能力：能根据用户需求（如目标受众、类型片种、场景数量限制等）灵活调整剧本的语感、尺度、叙事密度和节拍。
- 戏剧强化能力：在忠实于原作精神内核的前提下，能恰如其分地注入戏剧张力，丰富场次表现力，提升剧本的可拍性与观赏性。

[任务]
将用户输入的故事原文及可选定制需求，改编为按场次分割的专业剧本。输出必须是一个完整的场次列表，每一场都是发生在同一时间、同一地点内的连续戏剧动作单元。

[输入]
你将接收包含在 <STORY> 与 </STORY> 标签内的故事内容，以及包含在 <CHARACTERS> 与 </CHARACTERS> 标签内的人物描述，以及包含在 <REQUIREMENT> 与 </REQUIREMENT> 标签内的用户需求。
- 故事：一段完整或片段化的叙事文本，可能涵盖一场或多场的内容，提供情节、人物、对白及背景描写。
- 人物：从故事中抽取的人物卡片数组，可用于确定角色在各场内的出场、称呼与身份。
- 用户需求（可选）：该项可为空。具体可包含：
    - 目标受众（如少儿、青少年、成年人）
    - 剧本类型（如院线电影、网络长剧、微短剧）
    - 期望场次数（如"切分为5场"）
    - 其他特殊指令（如强化对白信息量、强化动作设计、使用快节奏剪辑语言等）

[输出]
{format_instructions}

[指南]
- **输出语言一致性**：输出中所有值的内容语言必须与输入故事的语言保持一致，不得混用。
- **分场划分准则**：以时间和空间的变更为硬性转场依据。每当时间（含闪回/闪前）或地点（含同一空间中显著的功能分区转换）发生改变，必须启用新场次。若用户指定了期望场次数量，应在满足时空逻辑的前提下尽可能匹配；否则依照故事本身的内在节奏进行自然分场，确保每一场都具备独立的戏剧任务或情绪推进。
- **剧本格式标准**：严格采用影视工业可执行标准格式。场标（场景标题）使用全大写或加粗，包含地点、时间及内外景标识（如"内. 咖啡馆 - 黄昏"）；人物名称在对话前居中对齐或全大写；对白另起行并缩进；动作描写与舞台指示置于括号内，且全部使用现在时。
- **连贯性与叙事流**：保证场景间的转场自然流畅，避免情节跳跃或逻辑断层。可运用视觉衔接、声音转场或情绪延续等视听手法来维系整体叙事节拍。
- **可视化描写的铁律**：所有描述必须是"可被镜头直接拍摄"的具象内容。禁止使用抽象心理词汇，必须转化为外部动作与视觉元素（如"他马上避开对视，耳根泛红"代替"他感到羞愧"）。需充分描写环境细节（如光源方向、道具陈设、天气状态等）以强化氛围。人物表演需通过面部微表情、肢体动作与行为细节来外化内心状态（如"她咬住下唇，手指攥紧包带直发抖"暗示紧张）。
- **精神内核一致性**：确保所有对白、行为及情节调度与原始故事意图保持统一，不偏离核心情节支线，不篡改既定人物基底。
"""


HUMAN_PROMPT_WRITE_SCRIPT = """\
<STORY>
{story}
</STORY>

<CHARACTERS>
{characters}
</CHARACTERS>

<REQUIREMENT>
{requirement}
</REQUIREMENT>
"""


class Scene(BaseModel):
    scene_id: int = Field(..., description="场次编号")
    heading: str = Field(..., description="场景标题（如：内. 地点 - 白天）")
    action: str = Field(..., description="该场景的动作/描述")


class ScriptResponse(BaseModel):
    script: List[Scene] = Field(
        ...,
        description="根据故事生成的剧本。每个元素为一个场景，包含场次编号、场景标题及动作/描述。",
    )


class ScriptWriter:
    def __init__(self, model: str, api_key: str, base_url: str):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    async def write_script(
        self,
        story: str,
        characters_text: Optional[str] = None,
        user_requirement: Optional[str] = None,
    ) -> list[dict]:
        parser = PydanticOutputParser(pydantic_object=ScriptResponse)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT_WRITE_SCRIPT.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(content=HUMAN_PROMPT_WRITE_SCRIPT.format(
                story=story,
                characters=characters_text or "",
                requirement=user_requirement,
            )),
        ]

        content = await LLM.chat(self._model, messages, self._api_key, self._base_url)
        response = parser.parse(content)
        scenes = [
            {
                "title": s.heading or "",
                "content": s.action,
            }
            for s in response.script
        ]
        return scenes
