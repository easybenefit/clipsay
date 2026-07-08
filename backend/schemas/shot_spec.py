from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

class ShotBrief(BaseModel):
    idx: int = Field(
        description="该镜头在整部剧本镜头序列中的全局序号，从0开始。",
        examples=[0, 1, 2],
    )
    is_last: bool = Field(
        description="是否为全片最后一个镜头。若为 True，表示故事已完全结束，此镜之后不再规划任何镜头。",
        examples=[False, True],
    )
    cam_idx: int = Field(
        description="该镜头在当前场次中的机位编号。",
        examples=[0, 1, 2],
    )
    visual_desc: Optional[str] = Field(
        default=None,
        description=(
            "一段生动且详细的镜头视觉描述，通过文字传达丰富的画面信息。描述中出现的所有角色标识符必须与角色列表完全一致，并使用尖括号括起（例如 <张伟>、<李娜>）。所有处于可见状态的角色均需予以描述。若镜头内存在对话，请使用双引号给出对话内容，并附带该角色的特征说明"
            "（例如 <王强>（男，20多岁，略带东北口音，嗓音沉稳，神情专注）说：“起落架已锁定，襟翼收起，可以降落。”）。"
        ),
        examples=[
            "过肩平视镜头，机位在 <张伟> 身后。前景中 <张伟> 的肩与头部被柔焦处理，使视觉焦点落于 <李娜> 的面部。<李娜> 微妙的神情变化——由惊讶转为欣喜——清晰可见。超市背景在冷色调荧光灯下被轻微虚化。",
        ],
    )
    audio_desc: Optional[str] = Field(
        default=None,
        description="该镜头的音频详细描述，可涵盖环境音、音效、对白等。",
        examples=[
            "[音效] 环境声（超市背景噪声、购物车轮滚动声）",
            "[对白] 李娜（开心地）：你好，最近怎么样？",
            None,
        ],
    )

class ShotSpec(BaseModel):
    idx: int = Field(
        description="镜头在当前序列中的索引，从 0 开始。",
    )
    is_last: bool = Field(
        description="是否为当前序列中的最后一个镜头。若为 True，则此镜之后不再规划任何镜头。",
    )

    cam_idx: int = Field(
        description="该镜头在当前场次中的机位编号。",
        examples=[0, 1, 2],
    )
    visual_desc: str = Field(
        description=(
            "一段生动且详细的镜头视觉描述，通过文字传达丰富的画面信息。描述中出现的所有角色标识符必须与角色列表完全一致，并使用尖括号括起（例如 <Alice>、<Bob>）。"
            "若镜头中存在对话，请在视觉描述中写出对话内容。"
        ),
    )
    variation_type: Literal["large", "medium", "small"] = Field(
        description="表示该镜头内容相较于前一镜头的变化程度。",
        examples=["large", "medium", "small"],
    )
    variation_reason: str = Field(
        default="",
        description="说明该镜头内容变化程度的原因。",
    )

    sf_dec: str = Field(description="镜头首帧的详细描述。")
    sf_vis_char_idxs: List[int] = Field(
        default_factory=list,
        description="首帧中可见的角色索引列表。",
    )
    sf_desc: str = Field(description="镜头末帧的详细描述。")
    ef_vis_char_idxs: List[int] = Field(
        default_factory=list,
        description="末帧中可见的角色索引列表。",
    )
    motion_desc: str = Field(description="该镜头内运动（运镜、演员调度）的描述。")

    audio_desc: Optional[str] = Field(
        default=None,
        description="该镜头的音频详细描述，可包含环境音、音效、对白等。",
    )
