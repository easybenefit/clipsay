"""ShotOrchestrator — camera-tree assembly, transition-video extraction, first-frame generation.

:class:`ShotOrchestrator` does three things:

* :meth:`construct_camera_tree` — given a list of cameras and their
  shot descriptions, asks an LLM to assign each non-root camera a
  parent camera and a parent shot.  The resulting tree lets the
  transition generator reuse the parent's last frame when rendering
  each child's first frame, so i2v calls don't have to hallucinate
  the background.
* :meth:`generate_transition_video` + :meth:`get_new_camera_image`
  — render a transition between two consecutive cameras and pull
  the second camera's first frame from the result via scene detection.
* :meth:`generate_first_frame` — render a single shot's first frame
  from its :class:`ShotSpec` and a set of character portraits.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple, Union

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from moviepy import VideoFileClip
from PIL import Image
from pydantic import BaseModel, Field
from scenedetect import SceneManager, open_video, split_video_ffmpeg
from scenedetect.detectors import ContentDetector

from schemas import (
    CameraSetup,
    ImageOutput,
    ShotBrief,
    ShotSpec,
    VideoOutput,
)


system_prompt_template_select_reference_camera = \
"""
[Role]
You are a video editor. You build the hierarchical "shot tree" for a scene so the transition generator can reuse parent content when rendering child shots.

[Goal]
Given a sequence of cameras with their shot descriptions, assign each non-root camera a parent camera and a parent shot.

[Input]
A sequence of cameras, enclosed in <CAMERA_SEQ> / </CAMERA_SEQ>. Each camera's shots are inside <CAMERA_N> / </CAMERA_N>, where N is the camera index.

Example:
<CAMERA_SEQ>
<CAMERA_0>
Shot 0: Medium shot of the street. Alice and Bob are walking towards each other.
Shot 2: Medium shot of the street. Alice and Bob hug each other.
</CAMERA_0>
<CAMERA_1>
Shot 1: Close-up of Alice's face. Her expression shifts from surprise to delight as she recognizes Bob.
</CAMERA_1>
</CAMERA_SEQ>

[Output]
{format_instructions}

[Rules]
1. Language of all output values must match the input.
2. Content inclusion — a parent camera should, in at least one of its shots, fully contain the child camera's content. A medium two-shot parent, for example, can contain an over-the-shoulder reverse child.
3. Smoothness — prefer parents whose shot size is close to the child's. Avoid wide-to-close jumps unless no alternative exists.
4. Temporal proximity — locate the parent by the index closest to the child's first shot.
5. Acyclicity — the tree has no cycles. If a camera has multiple candidate parents, pick the best (closest shot size + content). If none fit, set parent to None.
6. Tie-break — when two cameras are mutual candidates, the lower-index one is the parent.
7. Single root — exactly one root camera is allowed, and it is the first camera in the sequence.
8. Note the missing content — capture what the child shot needs that the parent doesn't cover (e.g., the frontal view of Character A may be missing in a side-profile child shot).
"""


human_prompt_template_select_reference_camera = \
"""
<CAMERA_SEQ>
{camera_seq_str}
</CAMERA_SEQ>
"""


class CameraTreeNode(BaseModel):
    parent_cam_idx: Optional[int] = Field(
        default=None,
        description="The index of the parent camera. Set to None if the camera has no parent (e.g., root).",
        examples=[0, 1, None],
    )
    parent_shot_idx: Optional[int] = Field(
        default=None,
        description="The index of the parent shot. Set to None if the camera has no parent.",
        examples=[0, 3, None],
    )
    reason: str = Field(
        description="The reason for the parent camera selection. If root, explain why no parent fits.",
        examples=[
            "The parent shot's field of view covers the child shot's (medium -> close-up).",
            "The parent and child form a shot/reverse-shot pair.",
            "CAMERA_0 (Shot 0) establishes the entire scene and contains all characters and the setting. It is the root.",
        ],
    )
    is_parent_fully_covers_child: Optional[bool] = Field(
        default=None,
        description="Whether the parent shot fully covers the child shot's content. None if no parent.",
        examples=[True, False, None],
    )
    missing_info: Optional[str] = Field(
        default=None,
        description="Elements in the child shot not covered by the parent shot. None if fully covered.",
        examples=[
            "The frontal view of Alice.",
            None,
        ],
    )


class CameraTree(BaseModel):
    camera_parent_items: List[Optional[CameraTreeNode]] = Field(
        description="Parent items for each camera in input order. None for a root camera. "
                    "Length must equal the number of cameras.",
    )


class ShotOrchestrator:
    def __init__(self, chat_model, image_generator, video_generator) -> None:
        self.chat_model = chat_model
        self.image_generator = image_generator
        self.video_generator = video_generator

    async def construct_camera_tree(
        self,
        cameras: List[CameraSetup],
        shot_descs: List[Union[ShotSpec, ShotBrief]],
    ) -> List[CameraSetup]:
        parser = PydanticOutputParser(pydantic_object=CameraTree)

        camera_seq_str = "<CAMERA_SEQ>\n"
        for cam in cameras:
            camera_seq_str += f"<CAMERA_{cam.idx}>\n"
            for shot_idx in cam.active_shot_idxs:
                camera_seq_str += f"Shot {shot_idx}: {shot_descs[shot_idx].visual_desc}\n"
            camera_seq_str += f"</CAMERA_{cam.idx}>\n"
        camera_seq_str += "</CAMERA_SEQ>"

        messages = [
            SystemMessage(content=system_prompt_template_select_reference_camera.format(format_instructions=parser.get_format_instructions())),
            HumanMessage(content=human_prompt_template_select_reference_camera.format(camera_seq_str=camera_seq_str)),
        ]

        chain = self.chat_model | parser
        response: CameraTree = await chain.ainvoke(messages)
        for cam, parent_cam_item in zip(cameras, response.camera_parent_items):
            cam.parent_cam_idx = parent_cam_item.parent_cam_idx if parent_cam_item is not None else None
            cam.parent_shot_idx = parent_cam_item.parent_shot_idx if parent_cam_item is not None else None
            cam.reason = parent_cam_item.reason if parent_cam_item is not None else None
            cam.is_parent_fully_covers_child = parent_cam_item.is_parent_fully_covers_child if parent_cam_item is not None else None
            cam.missing_info = parent_cam_item.missing_info if parent_cam_item is not None else None
        return cameras

    async def generate_transition_video(
        self,
        first_shot_visual_desc: str,
        second_shot_visual_desc: str,
        first_shot_ff_path: str,
    ) -> VideoOutput:
        prompt = (
            f"Two shots. The transition between the shots is a cut to. The style of "
            f"the two shots should be consistent.\n"
            f"The first shot description: {first_shot_visual_desc}.\n"
            f"The second shot description: {second_shot_visual_desc}."
        )
        return await self.video_generator.generate_single_video(
            prompt=prompt,
            reference_image_paths=[first_shot_ff_path],
        )

    def get_new_camera_image(self, transition_video_path: str) -> ImageOutput:
        video = open_video(transition_video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector())
        scene_manager.detect_scenes(video, show_progress=False)
        scene_list = scene_manager.get_scene_list()
        output_dir = os.path.join(os.path.dirname(transition_video_path), "cache")
        os.makedirs(output_dir, exist_ok=True)
        split_video_ffmpeg(transition_video_path, scene_list, output_dir, show_progress=True)

        video_name = os.path.basename(transition_video_path).split('.')[0]
        second_video_path = os.path.join(output_dir, f"{video_name}-Scene-002.mp4")
        if os.path.exists(second_video_path):
            clip = VideoFileClip(second_video_path)
            ff = Image.fromarray(clip.get_frame(0).astype('uint8'), 'RGB')
            return ImageOutput(fmt="pil", ext="png", data=ff)

        # Fall back to the last frame of the transition video.
        clip = VideoFileClip(transition_video_path)
        lf_time = max(0, clip.duration - (1 / clip.fps))
        lf = Image.fromarray(clip.get_frame(lf_time).astype('uint8'), 'RGB')
        return ImageOutput(fmt="pil", ext="png", data=lf)

    async def generate_first_frame(
        self,
        shot_desc: ShotSpec,
        character_portrait_path_and_text_pairs: List[Tuple[str, str]],
        text_prompt: Optional[str] = None,
        style: str = "",
    ) -> ImageOutput:
        """Render a single first-frame image for ``shot_desc``.

        Args:
            shot_desc: the shot to render the first frame for.  ``ff_desc``
                is used when ``text_prompt`` is not supplied.
            character_portrait_path_and_text_pairs: ``(path, text)``
                pairs in the order they should appear in the prompt.
                Used both as reference images for the i2i call and as
                text captions when the caller does not supply
                ``text_prompt``.
            text_prompt: optional generation prompt from
                :class:`agents.ReferenceImagePicker`.  When supplied it
                replaces the default prompt and is taken verbatim.
            style: optional visual-style descriptor appended to the
                prompt.  Empty by default.
        """
        reference_image_paths = [path for path, _ in character_portrait_path_and_text_pairs]
        if text_prompt is not None:
            prompt = text_prompt
        else:
            prompt = ""
            for i, (_, text) in enumerate(character_portrait_path_and_text_pairs):
                prompt += f"Image {i}: {text}\n"
            prompt += f"Generate an image based on the following description: {shot_desc.ff_desc}."
        if style:
            prompt = f"{prompt}\nVisual style: {style}."
        return await self.image_generator.generate_single_image(
            prompt=prompt,
            reference_image_paths=reference_image_paths,
            size="1600x900",
        )
