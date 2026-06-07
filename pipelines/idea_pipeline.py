"""IdeaPipeline — top-level Clipsay pipeline.

Pipeline stages (all wired into :class:`streamlit_app.progress.ProgressTracker`):

1. **develop_story** — expand the idea into a full story via
   :class:`agents.StoryDeveloper`.
2. **extract_characters** — pull the cast and their visual descriptions
   via :class:`agents.CharacterExtractor`.
3. **portraits** — render front / side / back reference sheets for the
   first few characters via :class:`agents.PortraitGenerator`.
4. **write_script** — slice the story into per-scene scripts via
   :class:`agents.ScriptWriter`.
5. **scene_<N>** — for each scene, invoke the (currently stubbed)
   :class:`ScenePipeline` to produce a per-scene video clip.
6. **concat_final** — concatenate the per-scene clips with moviepy.

State is cached on disk under ``working_dir`` so re-runs only recompute
the stages whose output files are missing.  The cache is keyed by stage
name and the relevant inputs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional

from langchain.chat_models import init_chat_model
from moviepy import VideoFileClip, concatenate_videoclips
import yaml

from agents import (
    CharacterExtractor,
    PortraitGenerator,
    ScriptWriter,
    StoryDeveloper,
)
from schemas import CharacterInScene
from streamlit_app.progress import ProgressTracker
from clients.render_factory import RenderFactory
from utils.providers import (
    resolve_chat_model_config,
    strip_internal_resolve_keys,
    validate_resolved_chat_model_config,
)


class IdeaPipeline:
    """End-to-end idea-to-video pipeline."""

    def __init__(
        self,
        chat_model,
        image_generator,
        video_generator,
        working_dir: str,
        progress_tracker: Optional[ProgressTracker] = None,
    ):
        self.chat_model = chat_model
        self.image_generator = image_generator
        self.video_generator = video_generator
        self.working_dir = working_dir
        self.progress_tracker = progress_tracker
        os.makedirs(self.working_dir, exist_ok=True)

        self.story_developer = StoryDeveloper(chat_model=self.chat_model)
        self.script_writer = ScriptWriter(chat_model=self.chat_model)
        self.character_extractor = CharacterExtractor(chat_model=self.chat_model)
        self.portrait_generator = PortraitGenerator(
            image_generator=self.image_generator,
        )

    def _progress(self, phase: str, status: str, detail: str = "", step_progress: Optional[float] = None) -> None:
        if self.progress_tracker is not None:
            self.progress_tracker.update(phase, status, detail, step_progress)

    @classmethod
    def init_from_config(cls, config_path: str) -> "IdeaPipeline":
        """Build a pipeline from a parsed Clipsay YAML config."""
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        chat_args = resolve_chat_model_config(config["chat_model"]["init_args"])
        validate_resolved_chat_model_config(chat_args)
        strip_internal_resolve_keys(chat_args)
        chat_model = init_chat_model(**chat_args)
        render_factory = RenderFactory.from_config(config)

        return cls(
            chat_model=chat_model,
            image_generator=render_factory.image_generator,
            video_generator=render_factory.video_generator,
            working_dir=config["working_dir"],
        )

    # ── stage: extract characters ──────────────────────────────────────

    async def extract_characters(self, story: str) -> List[CharacterInScene]:
        save_path = os.path.join(self.working_dir, "characters.json")
        if os.path.exists(save_path):
            with open(save_path, "r", encoding="utf-8") as f:
                characters = json.load(f)
            characters = [CharacterInScene.model_validate(c) for c in characters]
            logging.info(f"Loaded {len(characters)} characters from cache.")
            self._progress("extract_characters", "completed",
                           f"Loaded {len(characters)} characters from cache")
            return characters

        self._progress("extract_characters", "running", "Extracting characters...")
        characters = await self.character_extractor.extract_characters(story)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump([c.model_dump() for c in characters], f, ensure_ascii=False, indent=4)
        logging.info(f"Extracted {len(characters)} characters; saved to {save_path}.")
        self._progress("extract_characters", "completed",
                       f"Extracted {len(characters)} characters")
        return characters

    # ── stage: character portraits ─────────────────────────────────────

    async def generate_character_portraits(
        self,
        characters: List[CharacterInScene],
        character_portraits_registry: Optional[Dict[str, Dict[str, Dict[str, str]]]],
        style: str,
    ) -> Dict[str, Dict[str, Dict[str, str]]]:
        registry_path = os.path.join(self.working_dir, "character_portraits_registry.json")
        if character_portraits_registry is None:
            if os.path.exists(registry_path):
                with open(registry_path, "r", encoding="utf-8") as f:
                    character_portraits_registry = json.load(f)
            else:
                character_portraits_registry = {}

        self._progress("portraits", "running",
                       f"Generating portraits for {len(characters)} characters...")
        to_generate = [
            c for c in characters
            if c.identifier_in_scene not in character_portraits_registry
        ]
        total = len(to_generate)
        done = 0

        if to_generate:
            tasks = [
                asyncio.create_task(
                    self.generate_portraits_for_single_character(c, style)
                )
                for c in to_generate
            ]
            for future in asyncio.as_completed(tasks):
                result = await future
                character_portraits_registry.update(result)
                done += 1
                self._progress(
                    "portraits", "running",
                    f"Portrait {done}/{total}",
                    step_progress=done / total if total else 1.0,
                )
                with open(registry_path, "w", encoding="utf-8") as f:
                    json.dump(character_portraits_registry, f, ensure_ascii=False, indent=4)
            self._progress("portraits", "completed",
                           f"Portraits for {len(characters)} characters")
        else:
            self._progress("portraits", "completed", "All portraits cached, skipped")

        return character_portraits_registry

    # ── stage: develop story ───────────────────────────────────────────

    async def develop_story(self, idea: str, user_requirement: str) -> str:
        save_path = os.path.join(self.working_dir, "story.txt")
        if os.path.exists(save_path):
            with open(save_path, "r", encoding="utf-8") as f:
                story = f.read()
            logging.info("Loaded story from cache.")
            self._progress("develop_story", "completed", "Loaded from cache")
            return story

        self._progress("develop_story", "running", "Developing story...")
        story = await self.story_developer(
            idea=idea, user_requirement=user_requirement,
        )
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(story)
        logging.info(f"Developed story; saved to {save_path}.")
        self._progress("develop_story", "completed", "Story developed")
        return story

    # ── stage: write script (story -> scene scripts) ──────────────────

    async def write_script_based_on_story(
        self, story: str, user_requirement: str,
    ) -> List[str]:
        save_path = os.path.join(self.working_dir, "script.json")
        if os.path.exists(save_path):
            with open(save_path, "r", encoding="utf-8") as f:
                script = json.load(f)
            logging.info("Loaded script from cache.")
            self._progress("write_script", "completed",
                           f"Loaded {len(script)} scenes from cache")
            return script

        self._progress("write_script", "running", "Writing script...")
        script = await self.script_writer(
            story=story, user_requirement=user_requirement,
        )
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=4)
        self._progress("write_script", "completed",
                       f"Written {len(script)} scenes")
        return script

    # ── helper: per-character portraits ───────────────────────────────

    async def generate_portraits_for_single_character(
        self,
        character: CharacterInScene,
        style: str,
    ) -> Dict[str, Dict[str, Dict[str, str]]]:
        character_dir = os.path.join(
            self.working_dir, "character_portraits",
            f"{character.idx}_{character.identifier_in_scene}",
        )
        os.makedirs(character_dir, exist_ok=True)

        front_path = os.path.join(character_dir, "front.png")
        if not os.path.exists(front_path):
            out = await self.portrait_generator.generate_front_portrait(character, style)
            out.save(front_path)

        side_path = os.path.join(character_dir, "side.png")
        if not os.path.exists(side_path):
            out = await self.portrait_generator.generate_side_portrait(character, front_path)
            out.save(side_path)

        back_path = os.path.join(character_dir, "back.png")
        if not os.path.exists(back_path):
            out = await self.portrait_generator.generate_back_portrait(character, front_path)
            out.save(back_path)

        logging.info(f"Completed character portraits for {character.identifier_in_scene}.")
        return {
            character.identifier_in_scene: {
                "front": {"path": front_path,
                          "description": f"A front view portrait of {character.identifier_in_scene}."},
                "side": {"path": side_path,
                         "description": f"A side view portrait of {character.identifier_in_scene}."},
                "back": {"path": back_path,
                         "description": f"A back view portrait of {character.identifier_in_scene}."},
            }
        }

    # ── main entry point ──────────────────────────────────────────────

    async def __call__(self, idea: str, user_requirement: str, style: str) -> str:
        story = await self.develop_story(idea=idea, user_requirement=user_requirement)
        characters = await self.extract_characters(story=story)
        character_portraits_registry = await self.generate_character_portraits(
            characters=characters,
            character_portraits_registry=None,
            style=style,
        )
        scene_scripts = await self.write_script_based_on_story(
            story=story, user_requirement=user_requirement,
        )

        num_scenes = len(scene_scripts)
        if self.progress_tracker is not None:
            self.progress_tracker.set_num_scenes(num_scenes)

        # Defer the import so the missing per-scene pipeline can be
        # implemented (or stubbed) without breaking the import chain.
        from pipelines.scene_pipeline import ScenePipeline

        all_video_paths: List[str] = []
        for idx, scene_script in enumerate(scene_scripts):
            scene_phase = f"scene_{idx}"
            self._progress(
                scene_phase, "running",
                f"Processing scene {idx+1}/{num_scenes}",
                step_progress=(idx + 1) / num_scenes,
            )
            scene_working_dir = os.path.join(self.working_dir, f"scene_{idx}")
            os.makedirs(scene_working_dir, exist_ok=True)
            scene_pipeline = ScenePipeline(
                chat_model=self.chat_model,
                image_generator=self.image_generator,
                video_generator=self.video_generator,
                working_dir=scene_working_dir,
                progress_tracker=self.progress_tracker,
                progress_phase_prefix=f"scene_{idx}.",
            )
            final_video_path = await scene_pipeline(
                script=scene_script,
                user_requirement=user_requirement,
                style=style,
                characters=characters,
                character_portraits_registry=character_portraits_registry,
            )
            self._progress(scene_phase, "completed",
                           f"Scene {idx+1}/{num_scenes} done")
            all_video_paths.append(final_video_path)

        final_video_path = os.path.join(self.working_dir, "final_video.mp4")
        if os.path.exists(final_video_path):
            logging.info("Final video already exists; skipping concatenation.")
            self._progress("concat_final", "completed", "Final video already exists")
        else:
            self._progress("concat_final", "running", "Concatenating final video...")
            clips = [VideoFileClip(p) for p in all_video_paths]
            final = concatenate_videoclips(clips)
            final.write_videofile(final_video_path)
            self._progress("concat_final", "completed", "Final video ready")
        return final_video_path
