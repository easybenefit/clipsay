import os

from moviepy import VideoFileClip, concatenate_videoclips
from PIL import Image

from backend.utils.logging import setup_logger

_logger = setup_logger("video_compositor")


class VideoCompositor:
    @staticmethod
    def compose(video_paths: list[str], save_path: str) -> str:
        if os.path.exists(save_path):
            _logger.info("Skipped composing video, already exists: %s", save_path)
            return save_path
        if not video_paths:
            raise ValueError("No video paths provided")

        _logger.info("Composing %d video segments into %s...", len(video_paths), save_path)
        clips = [VideoFileClip(p) for p in video_paths]
        try:
            final = concatenate_videoclips(clips)
            final.write_videofile(save_path)
            _logger.info("Composed video saved to %s", save_path)
            return save_path
        finally:
            for clip in clips:
                try:
                    clip.close()
                except Exception:
                    pass

    @staticmethod
    def extract_first_frame(video_path: str, save_path: str) -> str:
        if os.path.exists(save_path):
            return save_path
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
        clip = VideoFileClip(video_path)
        try:
            frame = clip.get_frame(0)
            Image.fromarray(frame).save(save_path, quality=85)
            _logger.info("Extracted first frame to %s", save_path)
            return save_path
        finally:
            clip.close()
