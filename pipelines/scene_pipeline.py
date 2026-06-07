"""Per-scene video generation for Clipsay.

:class:`ScenePipeline` is the per-scene counterpart to
:class:`pipelines.idea_pipeline.IdeaPipeline`.  While the latter walks
the whole idea through storyboarding, character extraction, portrait
generation, and script writing, :class:`ScenePipeline` takes a single
scene and turns it into a single MP4.

The pipeline has six sub-phases, each reported to the progress
tracker under the parent's ``scene_<N>`` prefix (the parent
:class:`IdeaPipeline` folds them into the overall progress bar):

1. **storyboard** — :class:`agents.StoryboardArtist.design_storyboard`
   turns the scene script and cast into a list of
   :class:`schemas.ShotBrief`.
2. **visual_descs** — for each shot,
   :class:`agents.StoryboardArtist.decompose_visual_description`
   expands the brief into a :class:`schemas.ShotSpec` with first
   frame, last frame, and motion.
3. **camera_tree** — :class:`agents.ShotOrchestrator.construct_camera_tree`
   groups the shots by camera and asks the LLM to assign each
   non-root camera a parent camera and parent shot, populating the
   :class:`schemas.CameraSetup` list.
4. **frames** — per shot, in order:
   :class:`agents.ReferenceImagePicker` picks the best references
   from the running reference pool (visible-character portraits plus
   the previous shot's first frame), then
   :class:`agents.ShotOrchestrator.generate_first_frame` renders
   ``_NUM_CANDIDATE_FRAMES`` candidates, then
   :class:`agents.ImageScorer` picks the best of them.
5. **videos** — per shot, in order: an i2v call with the shot's
   first frame as the reference and a prompt that joins
   ``ff_desc``/``lf_desc``/``motion_desc``/``style``/``audio_desc``.
6. **concat** — :mod:`moviepy` concatenation of the per-shot videos
   into the scene's MP4.

All intermediate artifacts are cached under ``working_dir`` so re-runs
only recompute the stages whose output files are missing.  Cache files
are versioned by content only — changing ``style`` or
``user_requirement`` does not invalidate them, so users must delete
``working_dir`` to force a clean re-run after a prompt-relevant
change.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Dict, List, Optional, Tuple

from moviepy import VideoFileClip, concatenate_videoclips

from agents import (
    ImageScorer,
    ReferenceImagePicker,
    ShotOrchestrator,
    StoryboardArtist,
)
from schemas import (
    CameraSetup,
    CharacterInScene,
    ShotBrief,
    ShotSpec,
)
from streamlit_app.progress import ProgressTracker

_NUM_CANDIDATE_FRAMES = 4
_VIDEO_DURATION = 5
_VIDEO_ASPECT_RATIO = "16:9"


def _shot_briefs_to_json(shots: List[ShotBrief]) -> str:
    return json.dumps([s.model_dump() for s in shots], ensure_ascii=False, indent=2)


def _shot_briefs_from_json(raw: str) -> List[ShotBrief]:
    return [ShotBrief.model_validate(d) for d in json.loads(raw)]


def _shot_specs_to_json(specs: List[ShotSpec]) -> str:
    return json.dumps([s.model_dump() for s in specs], ensure_ascii=False, indent=2)


def _shot_specs_from_json(raw: str) -> List[ShotSpec]:
    return [ShotSpec.model_validate(d) for d in json.loads(raw)]


def _cameras_to_json(cameras: List[CameraSetup]) -> str:
    return json.dumps([c.model_dump() for c in cameras], ensure_ascii=False, indent=2)


def _cameras_from_json(raw: str) -> List[CameraSetup]:
    return [CameraSetup.model_validate(d) for d in json.loads(raw)]


def _build_cameras_from_shot_briefs(shot_briefs: List[ShotBrief]) -> List[CameraSetup]:
    """Group shots by ``cam_idx`` into :class:`CameraSetup` entries.

    The root camera (first distinct ``cam_idx``) is left with
    ``parent_cam_idx = None``; all other cameras start with ``None``
    parents and are populated by
    :meth:`agents.ShotOrchestrator.construct_camera_tree`.
    """
    by_cam: Dict[int, List[int]] = {}
    for shot in shot_briefs:
        by_cam.setdefault(shot.cam_idx, []).append(shot.idx)
    return [
        CameraSetup(idx=cam_idx, active_shot_idxs=sorted(shot_idxs))
        for cam_idx, shot_idxs in sorted(by_cam.items())
    ]


class ScenePipeline:
    """Render a single scene to an MP4 and return its path.

    Args:
        chat_model: the LangChain chat model used by the storyboard,
            camera-tree, reference-picker, and image-scorer agents.
        image_generator: any object satisfying
            :class:`clients.protocols.ImageGenerator`.
        video_generator: any object satisfying
            :class:`clients.protocols.VideoGenerator`.
        working_dir: scratch directory for this scene's intermediate
            files (shot briefs, specs, first-frame images, per-shot
            videos, final MP4).  Created on construction if missing.
        progress_tracker: optional callback sink; receives one update
            per pipeline sub-phase.
        progress_phase_prefix: prepended to every sub-phase name so
            the parent :class:`pipelines.IdeaPipeline` can fold the
            per-scene timeline into the overall progress bar
            (typically ``f"scene_{idx}."``).
    """

    def __init__(
        self,
        chat_model,
        image_generator,
        video_generator,
        working_dir: str,
        progress_tracker: Optional[ProgressTracker] = None,
        progress_phase_prefix: str = "",
    ):
        self.chat_model = chat_model
        self.image_generator = image_generator
        self.video_generator = video_generator
        self.working_dir = working_dir
        self.progress_tracker = progress_tracker
        self.progress_phase_prefix = progress_phase_prefix
        os.makedirs(self.working_dir, exist_ok=True)

        self._frames_dir = os.path.join(self.working_dir, "first_frames")
        self._videos_dir = os.path.join(self.working_dir, "shot_videos")
        os.makedirs(self._frames_dir, exist_ok=True)
        os.makedirs(self._videos_dir, exist_ok=True)

        self.storyboard_artist = StoryboardArtist(chat_model=self.chat_model)
        self.shot_orchestrator = ShotOrchestrator(
            chat_model=self.chat_model,
            image_generator=self.image_generator,
            video_generator=self.video_generator,
        )
        self.reference_picker = ReferenceImagePicker(chat_model=self.chat_model)
        self.image_scorer = ImageScorer(chat_model=self.chat_model)

    def _progress(
        self,
        phase: str,
        status: str,
        detail: str = "",
        step_progress: Optional[float] = None,
    ) -> None:
        if self.progress_tracker is not None:
            self.progress_tracker.update(
                f"{self.progress_phase_prefix}{phase}",
                status, detail, step_progress,
            )

    # ── sub-phase 1: storyboard ────────────────────────────────────────

    async def _storyboard(
        self,
        script: str,
        characters: List[CharacterInScene],
        user_requirement: Optional[str],
    ) -> List[ShotBrief]:
        cache_path = os.path.join(self.working_dir, "shot_briefs.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                briefs = _shot_briefs_from_json(f.read())
            self._progress("storyboard", "completed",
                           f"Loaded {len(briefs)} shots from cache")
            return briefs

        self._progress("storyboard", "running", "Designing storyboard...")
        briefs = await self.storyboard_artist.design_storyboard(
            script=script,
            characters=characters,
            user_requirement=user_requirement,
        )
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(_shot_briefs_to_json(briefs))
        logging.info("ScenePipeline: designed %d shots", len(briefs))
        self._progress("storyboard", "completed", f"Designed {len(briefs)} shots")
        return briefs

    # ── sub-phase 2: visual_descs ──────────────────────────────────────

    async def _decompose_shots(
        self,
        shot_briefs: List[ShotBrief],
        characters: List[CharacterInScene],
    ) -> List[ShotSpec]:
        cache_path = os.path.join(self.working_dir, "shot_specs.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                specs = _shot_specs_from_json(f.read())
            self._progress("visual_descs", "completed",
                           f"Loaded {len(specs)} specs from cache")
            return specs

        total = len(shot_briefs)
        self._progress("visual_descs", "running", f"Decomposing {total} shots...")
        specs: List[ShotSpec] = []
        for i, brief in enumerate(shot_briefs):
            spec = await self.storyboard_artist.decompose_visual_description(
                shot_brief_desc=brief,
                characters=characters,
            )
            specs.append(spec)
            self._progress(
                "visual_descs", "running",
                f"Shot {i + 1}/{total} decomposed",
                step_progress=(i + 1) / total if total else 1.0,
            )
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(_shot_specs_to_json(specs))
        logging.info("ScenePipeline: decomposed %d shots", total)
        self._progress("visual_descs", "completed", f"{total} shots decomposed")
        return specs

    # ── sub-phase 3: camera_tree ───────────────────────────────────────

    async def _build_camera_tree(
        self,
        shot_briefs: List[ShotBrief],
    ) -> List[CameraSetup]:
        cache_path = os.path.join(self.working_dir, "camera_tree.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cameras = _cameras_from_json(f.read())
            self._progress("camera_tree", "completed",
                           f"Loaded {len(cameras)} cameras from cache")
            return cameras

        self._progress("camera_tree", "running", "Building camera tree...")
        cameras = _build_cameras_from_shot_briefs(shot_briefs)
        cameras = await self.shot_orchestrator.construct_camera_tree(
            cameras=cameras,
            shot_descs=shot_briefs,
        )
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(_cameras_to_json(cameras))
        logging.info("ScenePipeline: built camera tree with %d cameras", len(cameras))
        self._progress("camera_tree", "completed",
                       f"Built camera tree with {len(cameras)} cameras")
        return cameras

    # ── sub-phase 4: frames ────────────────────────────────────────────

    def _portrait_pairs_for_indices(
        self,
        char_indices: List[int],
        characters: List[CharacterInScene],
        registry: Dict[str, Dict[str, Dict[str, str]]],
    ) -> List[Tuple[str, str]]:
        """Build ``(path, text)`` portrait pairs for the listed character indices."""
        pairs: List[Tuple[str, str]] = []
        for idx in char_indices:
            if idx < 0 or idx >= len(characters):
                continue
            char = characters[idx]
            if not char.is_visible:
                continue
            views = registry.get(char.identifier_in_scene) or {}
            front = views.get("front") or {}
            path = front.get("path")
            description = front.get("description") or f"A front view of {char.identifier_in_scene}."
            if not path or not os.path.exists(path):
                continue
            pairs.append((path, description))
        return pairs

    def _build_reference_pool(
        self,
        shot_spec: ShotSpec,
        characters: List[CharacterInScene],
        registry: Dict[str, Dict[str, Dict[str, str]]],
        previous_first_frame_path: Optional[str],
    ) -> List[Tuple[str, str]]:
        """Reference pool for a single shot's first-frame generation.

        Combines the visible-character portraits with the previous
        shot's first frame (for in-scene environmental continuity).
        """
        pool = self._portrait_pairs_for_indices(
            shot_spec.ff_vis_char_idxs, characters, registry,
        )
        if previous_first_frame_path and os.path.exists(previous_first_frame_path):
            pool.append((
                previous_first_frame_path,
                "The first frame of the previous shot, used for environmental continuity.",
            ))
        return pool

    async def _generate_first_frames(
        self,
        shot_specs: List[ShotSpec],
        characters: List[CharacterInScene],
        registry: Dict[str, Dict[str, Dict[str, str]]],
        style: str,
    ) -> List[str]:
        total = len(shot_specs)
        self._progress("frames", "running",
                       f"Generating first frames for {total} shots...")

        first_frame_paths: List[str] = []
        for i, spec in enumerate(shot_specs):
            ff_path = os.path.join(self._frames_dir, f"shot_{spec.idx:04d}.png")
            if os.path.exists(ff_path):
                first_frame_paths.append(ff_path)
                self._progress(
                    "frames", "running",
                    f"Frame {i + 1}/{total} cached",
                    step_progress=(i + 1) / total if total else 1.0,
                )
                continue

            previous_ff = first_frame_paths[-1] if first_frame_paths else None
            pool = self._build_reference_pool(spec, characters, registry, previous_ff)
            selection = await self.reference_picker.select_reference_images_and_generate_prompt(
                available_image_path_and_text_pairs=pool,
                frame_description=spec.ff_desc,
            )
            chosen_pairs = selection["reference_image_path_and_text_pairs"]
            text_prompt = selection["text_prompt"]

            candidate_paths: List[str] = []
            for c_idx in range(_NUM_CANDIDATE_FRAMES):
                cand = await self.shot_orchestrator.generate_first_frame(
                    shot_desc=spec,
                    character_portrait_path_and_text_pairs=chosen_pairs,
                    text_prompt=text_prompt,
                    style=style,
                )
                cand_path = os.path.join(self._frames_dir, f"shot_{spec.idx:04d}_c{c_idx}.png")
                cand.save(cand_path)
                candidate_paths.append(cand_path)

            best = await self.image_scorer(
                reference_image_path_and_text_pairs=chosen_pairs,
                target_description=spec.ff_desc,
                candidate_image_paths=candidate_paths,
            )
            shutil.copy(best, ff_path)
            first_frame_paths.append(ff_path)
            self._progress(
                "frames", "running",
                f"Frame {i + 1}/{total} ready",
                step_progress=(i + 1) / total if total else 1.0,
            )
        logging.info("ScenePipeline: %d first frames ready", total)
        self._progress("frames", "completed", f"{total} first frames ready")
        return first_frame_paths

    # ── sub-phase 5: videos ────────────────────────────────────────────

    def _build_animation_prompt(self, spec: ShotSpec, style: str) -> str:
        lines = []
        if style:
            lines.append(f"Visual style: {style}.")
        lines.append(f"Starting state: {spec.ff_desc}.")
        lines.append(f"Ending state: {spec.lf_desc}.")
        if spec.motion_desc:
            lines.append(f"Motion: {spec.motion_desc}.")
        if spec.audio_desc:
            lines.append(f"Audio: {spec.audio_desc}.")
        return "\n".join(lines)

    async def _animate_shots(
        self,
        shot_specs: List[ShotSpec],
        first_frame_paths: List[str],
        style: str,
    ) -> List[str]:
        total = len(shot_specs)
        self._progress("videos", "running", f"Animating {total} shots...")

        video_paths: List[str] = []
        for i, (spec, ff_path) in enumerate(zip(shot_specs, first_frame_paths)):
            shot_video_path = os.path.join(self._videos_dir, f"shot_{spec.idx:04d}.mp4")
            if os.path.exists(shot_video_path):
                video_paths.append(shot_video_path)
                self._progress(
                    "videos", "running",
                    f"Shot {i + 1}/{total} cached",
                    step_progress=(i + 1) / total if total else 1.0,
                )
                continue

            prompt = self._build_animation_prompt(spec, style)
            out = await self.video_generator.generate_single_video(
                prompt=prompt,
                reference_image_paths=[ff_path],
                aspect_ratio=_VIDEO_ASPECT_RATIO,
                duration=_VIDEO_DURATION,
            )
            out.save(shot_video_path)
            video_paths.append(shot_video_path)
            self._progress(
                "videos", "running",
                f"Shot {i + 1}/{total} animated",
                step_progress=(i + 1) / total if total else 1.0,
            )
        logging.info("ScenePipeline: %d shots animated", total)
        self._progress("videos", "completed", f"{total} shots animated")
        return video_paths

    # ── sub-phase 6: concat ────────────────────────────────────────────

    async def _concat_videos(self, video_paths: List[str]) -> str:
        self._progress("concat", "running", "Concatenating per-shot videos...")
        scene_path = os.path.join(self.working_dir, "scene.mp4")
        clips = [VideoFileClip(p) for p in video_paths]
        try:
            final = concatenate_videoclips(clips)
            final.write_videofile(scene_path)
        finally:
            for clip in clips:
                clip.close()
        logging.info("ScenePipeline: scene video written to %s", scene_path)
        self._progress("concat", "completed", "Scene video ready")
        return scene_path

    # ── main entry point ──────────────────────────────────────────────

    async def __call__(
        self,
        script: str,
        user_requirement: str,
        style: str,
        characters: List[CharacterInScene],
        character_portraits_registry: Dict,
    ) -> str:
        """Render one scene to an MP4 and return its path.

        Args:
            script: the screenplay script for this scene.
            user_requirement: the user's high-level intent, propagated
                through every stage.
            style: visual style applied to image and video prompts.
            characters: list of :class:`schemas.CharacterInScene` for
                this scene.
            character_portraits_registry: mapping of
                ``identifier -> view -> {"path": ..., "description": ...}``
                built by the parent :class:`IdeaPipeline`.

        Returns:
            The path to the per-scene MP4 (``<working_dir>/scene.mp4``).
        """
        shot_briefs = await self._storyboard(script, characters, user_requirement)
        await self._build_camera_tree(shot_briefs)
        shot_specs = await self._decompose_shots(shot_briefs, characters)

        first_frame_paths = await self._generate_first_frames(
            shot_specs, characters, character_portraits_registry, style,
        )
        video_paths = await self._animate_shots(shot_specs, first_frame_paths, style)
        return await self._concat_videos(video_paths)
