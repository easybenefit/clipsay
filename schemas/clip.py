"""Persistent clip records and the on-disk index that backs them.

A :class:`Clip` is the Streamlit console's view of a single video
production: title, status, image / video URLs or local paths, and the
idea that produced it.  :class:`ClipStore` reads / writes a JSON index
file so the gallery reloads after a server restart.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List, Literal, Optional

ClipStatus = Literal["new", "cancel", "progress", "stop", "success"]


@dataclass
class Clip:
    id: int
    title: str
    status: ClipStatus = "cancel"
    image_url: str = ""
    image_path: str = ""
    video_url: str = ""
    video_path: str = ""
    idea: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


class ClipStore:
    def __init__(self, index_path: str):
        self.index_path = index_path

    def load(self) -> List[Clip]:
        if not os.path.isfile(self.index_path):
            return []
        with open(self.index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        clips = []
        for item in data.get("clips", []):
            item["id"] = int(item["id"])
            clips.append(Clip(**item))
        return clips

    def save(self, clips: List[Clip]) -> None:
        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)
        data = {"clips": [asdict(c) for c in clips]}
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _next_id(self) -> int:
        clips = self.load()
        if not clips:
            return 1
        return max(c.id for c in clips) + 1

    def add(self, clip: Clip) -> Clip:
        clip.id = self._next_id()
        clips = self.load()
        clips.append(clip)
        self.save(clips)
        return clip

    def update(self, clip: Clip) -> None:
        clip.updated_at = datetime.now().isoformat(timespec="seconds")
        clips = self.load()
        for i, c in enumerate(clips):
            if c.id == clip.id:
                clips[i] = clip
                break
        self.save(clips)

    def get(self, clip_id: int | str) -> Optional[Clip]:
        if isinstance(clip_id, str):
            try:
                clip_id = int(clip_id)
            except ValueError:
                return None
        for c in self.load():
            if c.id == clip_id:
                return c
        return None

    def delete(self, clip_id: int | str) -> None:
        if isinstance(clip_id, str):
            try:
                clip_id = int(clip_id)
            except ValueError:
                return
        clips = self.load()
        clips = [c for c in clips if c.id != clip_id]
        self.save(clips)
