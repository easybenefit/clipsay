from __future__ import annotations

from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from backend.schemas.shot_spec import ShotBrief, ShotSpec
from backend.clients.llm import LLM
from backend.utils.logging import setup_logger

logger = setup_logger("storyboard_artist")


SYSTEM_PROMPT_DESIGN_STORYBOARD = \
    """
[角色]
你是一名专业的影视分镜师，具备以下核心能力：
- 剧本解读能力：能快速解析剧本文本，识别场景设置、人物动作、对话、情绪和叙事节奏。
- 视觉化能力：擅长将文字描述转化为可视分镜画面，包括构图、光线和空间布置。
- 分镜绘制能力：精通电影语言，如镜头类型（特写、中景、远景）、机位角度（俯拍、平等视角）、镜头运动（推、拉、摇、移）和转场。
- 叙事连贯性：能够确保分镜序列逻辑流畅、突出关键情节点并保持情绪一致。
- 技术素养：理解基础的分镜格式与行业标准，如使用编号镜头与简洁描述。

[任务]
你的任务是基于用户提供的剧本（仅包含单一场景）设计一份完整的分镜。分镜应以文本形式呈现，清晰展示每个镜头的视觉元素与叙事流程，帮助用户可视化该场景。

[输入]
你将收到以下输入：
- 剧本（SCRIPT）：一份完整的单场景剧本，包含对话、动作描写与场景设置。剧本只聚焦于一个场景，无需处理多场景切换。剧本内容封装在 <SCRIPT> 与 </SCRIPT> 标签内。
- 人物列表（CHARACTERS）：一组描述每个人物基本信息的列表，例如姓名、性格特征、外观（如相关）。人物列表封装在 <CHARACTERS> 与 </CHARACTERS> 标签内。
- 用户需求（USER_REQUIREMENT，可选）：封装在 <USER_REQUIREMENT> 与 </USER_REQUIREMENT> 标签内，可能包括：
    - 目标受众（如少儿、青少年、成年人）。
    - 分镜风格（如写实、卡通、抽象）。
    - 期望镜头数（如"不超过 10 个镜头"）。
    - 其它具体指令（如强调人物动作）。

[输出]
{format_instructions}

[指南]
- 确保所有输出值（除键名外）的语言与剧本语言一致。镜头类型、景别、角度、运动等术语必须使用中文（如远景、中景、特写、俯拍、推轨、摇摄、跟拍等），禁止使用英文术语（如 Full Shot、Close-up、Dolly、Pan 等）。
- 每个镜头必须有清晰的叙事目的——例如建立环境、展现人物关系或突出反应。
- 慎重使用电影语言：用特写表现情绪，用远景交代环境，用变化的角度引导观众注意力。
- 在设计新镜头时，先考虑是否能借助已有的机位进行拍摄。只有当景别、角度与焦点明显不同时才引入新机位。如果镜头发生显著运动，此后不能再使用该机位。
- 在视觉描述中保持人物名称与人物列表一致。视觉描述中人物名称需要用尖括号包裹（如 <Alice>），但对话和说话者字段不需要。
- 在描述视觉元素时，必须指明元素在画面中的位置。例如：角色 A 位于画面左侧，面朝右方，桌前有张桌子，桌子位于画面中心偏左。注意不要描述不可见的元素，例如不能看见的紧闭门后的人物不要描述。
- 视觉描述中应避免不安全内容（暴力、歧视等），必要时使用间接方式（声音、暗示性图像），并替换敏感元素（如用番茄酱代替血液）。
- 每个角色每个镜头最多一句对话，每个对话必须对应一个镜头。
- 每个镜头需要独立、自洽的描述，不互相引用。
- 当镜头聚焦于某角色时，需说明聚焦的具体身体部位。
- 描述人物时，必须指明其面朝方向。
- 最后一帧聚焦人物：若最后一帧用近景/特写聚焦某角色，应在 visual_desc 中显式说明该焦点（例如"聚集在 <Bob> 的手上"）。
"""


HUMAN_PROMPT_DESIGN_STORYBOARD = """\
<SCRIPT>
{script}
</SCRIPT>

<CHARACTERS>
{characters}
</CHARACTERS>

<USER_REQUIREMENT>
{user_requirement}
</USER_REQUIREMENT>
"""


SYSTEM_PROMPT_DECOMPOSE_VISUAL_DESCRIPTION = \
    """
[角色]
你是一名专业的视觉文本分析师，精通电影语言与镜头叙事。你的专长是把一段完整的镜头描述准确解构为三个核心部分：静态的首帧、静态的尾帧，以及连接它们的动态运动。

[任务]
你的任务是严谨且有洞察地把用户给出的镜头视觉文本描述切分为三个不同部分：
- 首帧描述：描述镜头起始的静态画面。重点关注构图元素、人物初始姿态、环境布局、光线、色彩等静态视觉要素。
- 尾帧描述：描述镜头结尾的静态画面。同样聚焦静态构图，但必须反映镜头运动或元素内部运动所造成的最终状态。
- 运动描述：描述首帧与尾帧之间发生的所有运动。这包括镜头自身运动（如静止、推进、拉出、摇、移、跟随、俯仰等）以及镜头内元素的运动（如角色移动、物体的位置变化、光线变化等）。这是整段描述中最动态的部分。对于角色的运动和变化，不能直接用角色名字称呼，必须根据角色可被观察到的外在特征来指代，尤其是像服装特征这种醒目的部分。

[输入]
你将收到一段镜头的视觉文本描述，它通常隐含或显式地包含起始状态、运动过程与结束状态的信息。
同时你会收到一组候选人物列表，每条包含 identifier 与特征。
- 视觉描述封装在 <VISUAL_DESC> 与 </VISUAL_DESC> 之间。
- 人物列表封装在 <CHARACTERS> 与 </CHARACTERS> 之间。

[输出]
{format_instructions}

[指南]
- 确保所有输出值（除键名外）的语言与剧本语言一致。镜头类型、景别、角度、运动等术语必须使用中文（如远景、中景、特写、俯拍、推轨、摇摄、跟拍等），禁止使用英文术语（如 Full Shot、Close-up、Dolly、Pan 等）。
- 起始帧与尾帧描述必须是纯粹的"定格画面"，不包含任何正在进行的动作（例如"他正要站起来"是不可接受的，应为"他坐在椅子上，身体微微前倾"）。
- 运动描述中必须明确区分镜头运动与镜头内物体的运动。尽可能使用专业电影术语（推轨、摇移、变焦等）精确描述镜头运动。
- 运动描述中不能直接使用角色名字称呼角色，应使用可视特征来指代。例如"Alice 正在走路"不可，应该写成"Alice（短发、穿着绿色裙子）正在走路"。
- 尾帧描述必须与首帧描述及运动描述逻辑一致。运动部分描述的所有动作必须在尾帧静态画面中得到体现。
- 如果输入描述在某些细节上模糊，可以基于上下文进行合理推断与补充，使三个部分完整流畅。但核心要素必须严格忠于输入文本。
- 使用准确、简洁、专业的描述语言。避免过于文学化的修辞（比喻、情感渲染），聚焦提供可被可视化的信息。
- 与输入的视觉描述类似，首帧与尾帧描述都应包含景别、角度、构图等细节。
- 以下是同一镜头内部（而非两个镜头之间）三种变化幅度：
    - large：通常涉及夸张的转场镜头，意味着画面构图与焦点发生显著变化（举例：从远景平稳过渡到特写），通常伴随明显的镜头运动（如无人机穿城俯拍）。
    - medium：常涉及新角色登场，或角色从背身转为面向镜头。
    - small：通常仅涉及较小的变化，例如表情变化、已有角色的姿态与动作变化（如走路、坐下、站起）、中等镜头运动（如摇、俯仰、跟随）。
- 描述人物时必须指明其面朝方向。
- 第一个镜头需要交代整个场景环境，尽可能使用最广的景别。
- 优先使用单一或最少机位完成叙事。
"""


HUMAN_PROMPT_DECOMPOSE_VISUAL_DESCRIPTION = """\
<VISUAL_DESC>
{visual_desc}
</VISUAL_DESC>

<CHARACTERS>
{characters}
</CHARACTERS>
"""


class _StoryboardResponse(BaseModel):
    storyboard: List[ShotBrief] = Field(
        description="该场次的完整故事板，包含每个镜头的视觉描述与音频描述。",
    )


class StoryboardGenerator:
    def __init__(self, model: str, api_key: str, base_url: str):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    async def design_storyboard(
        self,
        script: str,
        characters: List["CharacterRead"],
        user_requirement: Optional[str] = None,
    ) -> List[ShotBrief]:
        parser = PydanticOutputParser(pydantic_object=_StoryboardResponse)

        characters_str = "\n".join(
            f"Character {index}: (identifier) {char.identifier}; "
            f"(static) {char.appearance}; (dynamic) {char.attire}"
            for index, char in enumerate(characters)
        )
        user_requirement_str = (user_requirement or "").strip()

        messages = [
            SystemMessage(content=SYSTEM_PROMPT_DESIGN_STORYBOARD.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(content=HUMAN_PROMPT_DESIGN_STORYBOARD.format(
                script=(script or "").strip(),
                characters=characters_str,
                user_requirement=user_requirement_str,
            )),
        ]

        logger.info("=== StoryboardGenerator.design_storyboard Request ===")
        logger.info("Model: %s", self._model)
        logger.info("Script length: %d chars", len(script or ""))
        logger.info("Characters count: %d", len(characters))
        logger.info("UserRequirement: %s", user_requirement_str)

        content = await LLM.chat(self._model, messages, self._api_key, self._base_url)
        response: _StoryboardResponse = parser.parse(content)

        return response.storyboard

    # 把“画面描述”翻译成精确的“图层指令”——比如告诉绘图模块“背景只画山，前景只画人”，
    # 告诉视频模块“镜头要横移，并且小宇的手指在动”，从而显著提升多角色复杂场景下的生成准确率
    async def decompose_visual_description(
        self,
        shot_brief_desc: ShotBrief,
        characters: List["CharacterRead"],
    ) -> ShotSpec:
        parser = PydanticOutputParser(
            pydantic_object=_VisDescDecompositionResponse)

        visual_desc = (shot_brief_desc.visual_desc or "").strip()

        characters_str = "\n".join(
            f"{char.identifier}: "
            f"(static) {char.appearance}; "
            f"(dynamic) {char.attire}"
            for char in characters
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT_DECOMPOSE_VISUAL_DESCRIPTION.format(
                format_instructions=parser.get_format_instructions(),
            )),
            HumanMessage(content=HUMAN_PROMPT_DECOMPOSE_VISUAL_DESCRIPTION.format(
                visual_desc=visual_desc,
                characters=characters_str,
            )),
        ]

        logger.info(
            "=== StoryboardGenerator.decompose_visual_description Request ===")
        logger.info("Model: %s", self._model)
        logger.info("VisualDesc length: %d chars", len(visual_desc))
        logger.info("Characters count: %d", len(characters))

        content = await LLM.chat(self._model, messages, self._api_key, self._base_url)

        logger.info("-----------> content: %s", content)
        decomposition: _VisDescDecompositionResponse = parser.parse(content)

        logger.info(
            "=== StoryboardGenerator.decompose_visual_description Response ===")
        logger.info("variation_type: %s", decomposition.variation_type)

        return ShotSpec(
            idx=shot_brief_desc.idx,
            is_last=shot_brief_desc.is_last,
            cam_idx=shot_brief_desc.cam_idx,
            visual_desc=shot_brief_desc.visual_desc,
            variation_type=decomposition.variation_type,
            variation_reason=decomposition.variation_reason,
            sf_dec=decomposition.sf_dec,
            sf_vis_char_idxs=decomposition.sf_vis_char_idxs,
            sf_desc=decomposition.sf_desc,
            ef_vis_char_idxs=decomposition.ef_vis_char_idxs,
            motion_desc=decomposition.motion_desc,
            audio_desc=shot_brief_desc.audio_desc,
        )


class _VisDescDecompositionResponse(BaseModel):
    sf_dec: str = Field(
        description="镜头首帧的详细描述，捕捉起始的视觉元素与构图。",
    )
    sf_vis_char_idxs: List[int] = Field(
        description="首帧中可见角色的索引列表，与输入中提供的角色列表相对应。",
        examples=[[0], [1], [0, 1], []],
    )
    sf_desc: str = Field(
        description="镜头末帧的详细描述，捕捉结束时的视觉元素与构图。",
    )
    ef_vis_char_idxs: List[int] = Field(
        description="末帧中可见角色的索引列表，与输入中提供的角色列表相对应。",
        examples=[[0], [1], [0, 1], []],
    )
    motion_desc: str = Field(
        description="该镜头的运动描述。描述镜头内部的动态视觉变化（摄影机运镜与画面内元素的运动）。",
        examples=[
            "固定机位。一位女士（短发，身着绿色连衣裙）正朝镜头方向走来。",
            "从中景推轨推进至特写。一位男士（蓄须，身着白色T恤）朝镜头微笑。",
        ],
    )
    variation_type: str = Field(
        description="表示镜头首帧与末帧之间的变化程度。取值为 'large'、'medium' 或 'small'。",
    )
    variation_reason: str = Field(
        description="说明该镜头变化程度的原因。",
    )
