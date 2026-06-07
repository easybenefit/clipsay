"""Clipsay pipelines — top-level orchestration of multi-stage video generation.

Currently shipped:

* :class:`IdeaPipeline` — takes a one-line idea, develops a story,
  extracts characters, generates character portraits, scripts the
  story into scenes, then runs the per-scene pipeline for each scene
  and concatenates the resulting clips into a final video.
* :class:`ScenePipeline` — renders a single scene to a single MP4.
  Drives the six per-scene sub-phases (storyboard, visual_descs,
  camera_tree, frames, videos, concat) and caches every intermediate
  artifact under its ``working_dir`` so re-runs only recompute the
  stages whose outputs are missing.
"""

from .idea_pipeline import IdeaPipeline
from .scene_pipeline import ScenePipeline

__all__ = ["IdeaPipeline", "ScenePipeline"]
