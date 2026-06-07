from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

StepStatus = Literal["pending", "running", "completed", "failed"]


@dataclass
class StepState:
    name: str
    status: StepStatus = "pending"
    detail: str = ""
    progress: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


# Phase → overall weight mapping for Idea2Video pipeline
# The progress tracker uses these to compute overall_progress.
# Scene phases are dynamic (N scenes), computed separately.
PHASE_WEIGHTS: Dict[str, float] = {
    "develop_story": 0.08,
    "extract_characters": 0.05,
    "portraits": 0.10,
    "write_script": 0.05,
    "scene_prefix": 0.65,  # split across N scenes
    "concat_final": 0.07,
}

SCENE_SUB_WEIGHTS: Dict[str, float] = {
    "storyboard": 0.15,
    "visual_descs": 0.20,
    "camera_tree": 0.10,
    "frames": 0.35,
    "videos": 0.15,
    "concat": 0.05,
}


class ProgressTracker:
    def __init__(self):
        self.steps: Dict[str, StepState] = {}
        self.logs: List[str] = []
        self.current_phase: str = ""
        self.overall_progress: float = 0.0
        self.num_scenes: int = 0

    def log(self, message: str):
        self.logs.append(message)
        print(message)

    def update(
        self,
        phase: str,
        status: StepStatus,
        detail: str = "",
        step_progress: Optional[float] = None,
    ):
        if phase not in self.steps:
            self.steps[phase] = StepState(name=phase)
        session = self.steps[phase]
        session.status = status
        session.detail = detail
        session.timestamp = time.time()
        if step_progress is not None:
            session.progress = step_progress
        if status in ("running",):
            self.current_phase = phase
        self._recalc_overall()

    def set_num_scenes(self, n: int):
        self.num_scenes = n

    def _recalc_overall(self):
        total = 0.0

        for phase, weight in PHASE_WEIGHTS.items():
            if phase == "scene_prefix":
                continue
            s = self.steps.get(phase)
            if s is None or s.status == "pending":
                continue
            if s.status == "completed":
                total += weight
            elif s.status == "running":
                total += weight * (s.progress if s.progress > 0 else 0.3)
            elif s.status == "failed":
                total += weight * 0.1

        scene_weight = PHASE_WEIGHTS["scene_prefix"]
        if self.num_scenes > 0:
            per_scene = scene_weight / self.num_scenes
            for idx in range(self.num_scenes):
                scene_phase = f"scene_{idx}"
                s = self.steps.get(scene_phase)
                if s is None or s.status == "pending":
                    continue
                if s.status == "completed":
                    total += per_scene
                elif s.status == "running":
                    scene_p = 0.0
                    for sub_name, sub_w in SCENE_SUB_WEIGHTS.items():
                        sub = self.steps.get(f"{scene_phase}.{sub_name}")
                        if sub is None or sub.status == "pending":
                            continue
                        if sub.status == "completed":
                            scene_p += sub_w
                        elif sub.status == "running":
                            scene_p += sub_w * (sub.progress if sub.progress > 0 else 0.3)
                        elif sub.status == "failed":
                            scene_p += sub_w * 0.1
                    total += per_scene * scene_p

        self.overall_progress = min(total, 1.0)
