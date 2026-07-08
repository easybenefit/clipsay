from __future__ import annotations

from typing import Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser

from backend.clients.llm import LLM
from backend.utils.logging import setup_logger
from backend.schemas.camera import CameraNode, CameraTreeResponse

logger = setup_logger("camera_tree")


SYSTEM_PROMPT_SELECT_REFERENCE_CAMERA = """
[角色]
你是一名专业的视频剪辑专家，专精多机位镜头分析与场景结构建模。你深入了解电影语言，能够解读镜头尺寸（如远景、中景、特写）以及内容包含关系，并能据此推断机位之间的层级结构。

[任务]
你的任务是分析输入的机位数据，构造一个"机位树"。该树结构表示父机位内容涵盖子机位内容的关系。你需要为每个机位识别父机位（如果存在）以及依赖的镜头编号。如果某机位没有父机位，输出 None。

[输入]
输入是一组机位序列，封装在 <CAMERA_SEQ> 与 </CAMERA_SEQ> 标签内。
每个机位包含一组由其拍摄的镜头，封装在 <CAMERA_N> 与 </CAMERA_N> 标签内，N 是该机位的编号。

输入格式示例：

<CAMERA_SEQ>
<CAMERA_0>
镜头 0：街道的中景。张伟和李娜正朝彼此走去。
镜头 2：街道的中景。张伟和李娜拥抱在一起。
</CAMERA_0>
<CAMERA_1>
镜头 1：李娜面部的特写。当她认出张伟时，表情由惊讶转为欣喜。
</CAMERA_1>
</CAMERA_SEQ>

[输出]
{format_instructions}

[指南]
- 所有输出值（除键名外）的语言必须与输入语言一致。镜头类型、景别等术语必须使用中文（如远景、中景、特写等），禁止使用英文术语。
- 内容包含性检查：父机位应在某些镜头中尽可能完整地涵盖子机位的内容（例如：父画面是两个中景双人镜头涵盖子画面的过肩反向镜头）。通过比较关键词（人物、动作、场景）分析镜头描述，确保父镜头的视野覆盖子镜头的视野。
- 转场流畅度优先：偏好更大景别作为父机位，例如远景 -> 中景 或 中景 -> 特写。父节点与子节点的景别应尽量接近。除非绝对必要，不允许从长镜头直接过渡到特写。
- 时间临近性：每个机位由其首个镜头描述，基于首镜头描述定位父机位。父机位的镜头编号应尽可能接近子机位的首镜头编号。
- 逻辑一致性：机位树应该无环，避免循环依赖。如果某机位可被多个潜在父机位包含，选择最佳匹配（基于景别与内容）。如果没有合适的父机位，输出 None。
- 在缺少更广视角的情况下，选择视野重叠最多的镜头作为父镜头（或一个镜头也可以作为反向镜头的父镜头）。当两个机位互为对方的父镜头时，选择编号较小的作为较大编号机位的父机位。
- 树中只能有一个根机位（无父机位）。
- 当描述子镜头缺失的元素时，需要仔细比较父镜头与子镜头之间的细节。例如：父镜头是 A 与 B 相对的中景双人镜头（两人均侧对镜头），而子镜头是 A 的特写（A 正对镜头）。此时子镜头缺少 A 的正面视角信息。
- 第一个机位必须是机位树的根。
"""


HUMAN_PROMPT_SELECT_REFERENCE_CAMERA = """\
<CAMERA_SEQ>
{camera_seq_str}
</CAMERA_SEQ>
"""


def _get_visual_desc(shot: Any) -> str:
    if isinstance(shot, dict):
        return shot.get("visual_desc", "")
    val = getattr(shot, "visual_desc", None)
    return val if val is not None else str(shot)


def serialize_camera_seq(cameras: List[CameraNode], shot_descs: List[Any]) -> str:
    lines = ["<CAMERA_SEQ>"]
    for cam in cameras:
        lines.append(f"<CAMERA_{cam.idx}>")
        for shot_idx in cam.active_shot_idxs:
            if 0 <= shot_idx < len(shot_descs):
                lines.append(f"Shot {shot_idx}: {_get_visual_desc(shot_descs[shot_idx])}")
        lines.append(f"</CAMERA_{cam.idx}>")
    lines.append("</CAMERA_SEQ>")
    return "\n".join(lines)


def build_camera_nodes(shot_descs: List["ShotSpec"]) -> List[CameraNode]:
    cam_map: dict[int, CameraNode] = {}
    for shot_desc in shot_descs:
        cam_idx = shot_desc.cam_idx
        shot_idx = shot_desc.idx
        node = cam_map.get(cam_idx)
        if node is None:
            cam_map[cam_idx] = CameraNode(idx=cam_idx, active_shot_idxs=[shot_idx])
        else:
            node.active_shot_idxs.append(shot_idx)
    return list(cam_map.values())


async def _resolve_camera_parents(
    cameras: List[CameraNode],
    shot_descs: List[Any],
    model: str,
    api_key: str,
    base_url: str,
) -> None:
    parser = PydanticOutputParser(pydantic_object=CameraTreeResponse)
    camera_seq_str = serialize_camera_seq(cameras, shot_descs)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT_SELECT_REFERENCE_CAMERA.format(
            format_instructions=parser.get_format_instructions(),
        )),
        HumanMessage(content=HUMAN_PROMPT_SELECT_REFERENCE_CAMERA.format(
            camera_seq_str=camera_seq_str,
        )),
    ]

    content = await LLM.chat(model, messages, api_key, base_url)
    response: CameraTreeResponse = parser.parse(content)

    for cam, parent_item in zip(cameras, response.camera_parent_items):
        if parent_item is not None:
            for field in ("parent_cam_idx", "parent_shot_idx", "reason",
                          "is_parent_fully_covers_child", "missing_info"):
                setattr(cam, field, getattr(parent_item, field))


def validate_camera_nodes(cameras: List[CameraNode]) -> None:
    idx_map = {cam.idx: cam for cam in cameras}
    seen: set[int] = set()

    for start in cameras:
        if start.idx in seen:
            continue
        path: set[int] = set()
        cur = start
        while cur is not None and cur.idx not in seen:
            if cur.idx in path:
                raise ValueError(
                    f"Camera tree cycle detected involving camera {cur.idx}. "
                    f"Cycle: {' -> '.join(str(n) for n in path)} -> {cur.idx}. "
                    f"This would cause a permanent deadlock in frame generation."
                )
            path.add(cur.idx)
            seen.add(cur.idx)
            cur = idx_map.get(cur.parent_cam_idx)


def _log_tree_request(prefix: str, cameras: List[CameraNode], shot_descs: List[Any],
                      model: Optional[str] = None) -> None:
    logger.info("=== %s Request ===", prefix)
    if model:
        logger.info("Model: %s", model)
    logger.info("Camera count: %d", len(cameras))
    logger.info("Shot count: %d", len(shot_descs))


def _log_tree_response(prefix: str, cameras: List[CameraNode]) -> None:
    logger.info("=== %s Response ===", prefix)
    logger.info("Parent items returned: %d", len([c for c in cameras if c.parent_cam_idx is not None]))


class CameraTreeBuilder:

    @staticmethod
    async def build(
        shot_descs: List["ShotSpec"],
        model: str,
        api_key: str,
        base_url: str,
    ) -> List[CameraNode]:
        cameras = build_camera_nodes(shot_descs)

        _log_tree_request("CameraTreeBuilder", cameras, shot_descs, model)
        await _resolve_camera_parents(cameras, shot_descs, model, api_key, base_url)
        _log_tree_response("CameraTreeBuilder", cameras)

        validate_camera_nodes(cameras)
        return cameras
