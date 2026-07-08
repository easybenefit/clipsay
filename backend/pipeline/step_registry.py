"""Pipeline step registry — maps step names to executor functions
and defines downstream dependencies for the pipeline runner."""

from __future__ import annotations

from backend.pipeline.composite.project import composite_video
from backend.pipeline.scene_storyboard import generate_storyboards
from backend.pipeline.steps.characters import generate_characters
from backend.pipeline.steps.portraits import generate_portraits
from backend.pipeline.steps.scene_scripts import write_scene_scripts
from backend.pipeline.steps.scene_media import generate_scene_frames_and_videos
from backend.pipeline.steps.story import generate_story


STEP_EXECUTORS = {
    "story": generate_story,
    "characters": generate_characters,
    "portraits": generate_portraits,
    "scene_scripts": write_scene_scripts,
    "storyboard": generate_storyboards,
    "shot_frames": generate_scene_frames_and_videos,
    "composite_video": composite_video,
}


STEP_DOWNSTREAM = {
    "story": ["story", "characters", "portraits", "scene_scripts", "storyboard",
              "shot_frames", "composite_video"],
    "characters": ["characters", "portraits", "storyboard", "shot_frames", "composite_video"],
    "portraits": ["portraits", "shot_frames", "composite_video"],
    "scene_scripts": ["scene_scripts", "storyboard", "shot_frames", "composite_video"],
    "storyboard": ["storyboard", "shot_frames", "composite_video"],
    "shot_frames": ["shot_frames", "composite_video"],
    "composite_video": ["composite_video"],
}
