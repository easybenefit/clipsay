from __future__ import annotations

import base64
import logging
import os
import urllib.request
from typing import List, Optional

from moviepy import VideoFileClip
from PIL import Image

from backend.clients.video import Video as VideoClientAPI
from backend.core.types import ImageRef, VideoOutput, ImageOutput

logger = logging.getLogger("transition_video")


class TransitionGenerator:
    def __init__(self, model: str, api_key: str, base_url: str):
        self._model = model
        self._api_key = api_key
        self._base_url = base_url

    async def generate_single_video(
        self,
        prompt: str,
        reference_image_paths: List[str],
    ) -> VideoOutput:
        image_urls: list[str] = []
        for p in reference_image_paths:
            if p.startswith(("http://", "https://", "data:")):
                image_urls.append(p)
            elif os.path.exists(p):
                with open(p, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                image_urls.append(f"data:image/png;base64,{b64}")

        payload: dict = {"prompt": prompt, "aspect_ratio": "16:9"}
        if image_urls:
            payload["extra_body"] = {"image": image_urls}

        result, _ = await VideoClientAPI.generate(
            self._model, payload, self._api_key, self._base_url,
        )

        data = result.get("data", [])
        if not data:
            raise RuntimeError("No video data in response")
        url = data[0].get("url", "")
        if not url:
            raise RuntimeError("No url in response data")

        return VideoOutput(fmt="url", ext="mp4", data=url)

    async def generate(
        self,
        first_shot_visual_desc: str,
        second_shot_visual_desc: str,
        first_shot_ff_path: str,
        save_path: str,
        reference_candidates: Optional[List[ImageRef]] = None,
    ) -> None:
        prompt = (
            f"两个连续镜头，镜头间转场为硬切（Cut）。两镜头视觉风格须保持统一。"
            f"\n第一个镜头描述: {first_shot_visual_desc}."
            f"\n第二个镜头描述: {second_shot_visual_desc}."
        )
        ref_paths = [ref.url for ref in reference_candidates] if reference_candidates else []
        video_output = await self.generate_single_video(
            prompt=prompt,
            reference_image_paths=ref_paths,
        )
        url = video_output.data
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        urllib.request.urlretrieve(url, save_path)

    def _extract_video_frame(self, video_path: str, time_sec: float) -> Image.Image | None:
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            fps = clip.fps
            if duration is None or fps is None:
                raise ValueError("clip.duration or clip.fps is None")
            duration_f = float(duration)
            fps_f = float(fps)
            if duration_f <= 0 or fps_f <= 0:
                raise ValueError(f"invalid duration={duration_f} or fps={fps_f}")
            time_sec = max(0, min(time_sec, duration_f - (1 / max(fps_f, 1))))
            frame = clip.get_frame(time_sec)
            clip.close()
            return Image.fromarray(frame.astype('uint8'), 'RGB')
        except Exception as e:
            logger.warning("Failed to extract frame at %ss from %s: %s", time_sec, video_path, e)
            return None

    def extract_frame(
        self,
        transition_video_path: str,
    ) -> ImageOutput:
        from scenedetect import ContentDetector, SceneManager, open_video
        from scenedetect.scene_manager import split_video_ffmpeg

        try:
            video = open_video(transition_video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector())
            scene_manager.detect_scenes(video, show_progress=False)
            scene_list = scene_manager.get_scene_list()

            if scene_list:
                output_dir = os.path.join(os.path.dirname(transition_video_path), "cache")
                os.makedirs(output_dir, exist_ok=True)
                split_video_ffmpeg(transition_video_path, scene_list, output_dir, show_progress=True)

                video_name = os.path.basename(transition_video_path).split('.')[0]
                second_video_path = os.path.join(output_dir, f"{video_name}-Scene-002.mp4")
                if os.path.exists(second_video_path):
                    result = self._extract_video_frame(second_video_path, 0)
                    if result is not None:
                        return ImageOutput(fmt="pil", ext="png", data=result)
        except Exception as e:
            logger.warning("Scene detection failed (%s), trying alternative extraction", e)

        # Try extracting at various positions to find the second shot
        clip = VideoFileClip(transition_video_path)
        try:
            duration = float(clip.duration)
        except Exception:
            duration = 5.0
        finally:
            clip.close()

        # Probe positions: 40%, 50%, 60% — after the hard cut midpoint
        for fraction in (0.4, 0.5, 0.6, 0.0, -1.0):
            t = duration * fraction if fraction >= 0 else duration + fraction
            result = self._extract_video_frame(transition_video_path, t)
            if result is not None:
                logger.info("Extracted frame at %.1fs (%.0f%%) from %s",
                            t, fraction * 100, transition_video_path)
                return ImageOutput(fmt="pil", ext="png", data=result)

        logger.error("Could not extract any frame from %s, returning blank image", transition_video_path)
        blank = Image.new("RGB", (512, 512), (60, 60, 70))
        return ImageOutput(fmt="pil", ext="png", data=blank)
