from __future__ import annotations

import asyncio
import json
from typing import Any


class EventType:
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_PAUSED = "pipeline_paused"
    PIPELINE_RESUMED = "pipeline_resumed"
    PIPELINE_CANCELLED = "pipeline_cancelled"
    PIPELINE_FAILED = "pipeline_failed"
    PIPELINE_COMPLETED = "pipeline_completed"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    STEP_RETRY = "step_retry"
    EMIT_PROGRESS = "emit_progress"
    STORYBOARD_SCENE_READY = "storyboard_scene_ready"
    SHOT_FRAME_READY = "shot_frame_ready"
    SHOT_VIDEO_READY = "shot_video_ready"
    SHOT_VIDEO_PREVIEW_READY = "shot_video_preview_ready"
    SCENE_COMPOSITE_READY = "scene_composite_ready"
    FINAL_VIDEO_READY = "final_video_ready"
    PORTRAIT_IMAGE_STATUS = "portrait_image_status"
    TASK_STATUS = "task_status"


class EventEmitter:
    """Stateful, typed event publisher.

    All emit helpers take the project context internally, so callers no longer
    thread (project_id, bus, step_name) through every call. Created via
    ``EventEmitter(bus, project_id)`` (plain) or ``EventEmitter.for_step(...)``
    (auto-tags business events with a step name).
    """

    def __init__(self, bus: "EventBus", project_id: int, step: str = ""):
        self._bus = bus
        self._project_id = project_id
        self._step = step

    @classmethod
    def for_step(cls, bus: "EventBus", project_id: int, step: str) -> "EventEmitter":
        return cls(bus, project_id, step=step)

    async def _publish(self, event: dict) -> None:
        if self._step and "step" not in event:
            event["step"] = self._step
        await self._bus.publish(self._project_id, event)

    # ── pipeline lifecycle ────────────────────────────────────────────────

    async def pipeline_started(self) -> None:
        await self._publish({"type": EventType.PIPELINE_STARTED})

    async def pipeline_resumed(self) -> None:
        await self._publish({"type": EventType.PIPELINE_RESUMED})

    async def pipeline_cancelled(self) -> None:
        await self._publish({"type": EventType.PIPELINE_CANCELLED})

    async def pipeline_failed(self, error: str) -> None:
        await self._publish({"type": EventType.PIPELINE_FAILED, "error": error})

    async def pipeline_completed(self) -> None:
        await self._publish({"type": EventType.PIPELINE_COMPLETED})

    async def pipeline_paused(
        self,
        reason: str = "",
        error: str = "",
    ) -> None:
        event: dict = {"type": EventType.PIPELINE_PAUSED}
        if reason:
            event["reason"] = reason
        if error:
            event["error"] = error
        await self._publish(event)

    # ── step transitions (runner-level; step arg is explicit) ────────────

    async def step_start(self, step: str) -> None:
        await self._publish({"type": EventType.STEP_START, "step": step})

    async def step_complete(self, step: str, result: dict) -> None:
        await self._publish({
            "type": EventType.STEP_COMPLETE, "step": step, "result": result,
        })

    async def step_failed(self, step: str, error: str) -> None:
        await self._publish({
            "type": EventType.STEP_FAILED, "step": step, "error": error,
        })

    async def step_retry(
        self, step: str, attempt: int, max_retries: int, error: str,
    ) -> None:
        await self._publish({
            "type": EventType.STEP_RETRY,
            "step": step, "attempt": attempt, "max_retries": max_retries,
            "error": error,
        })

    async def emit_progress(
        self, step: str, progress: float, message: str = "",
    ) -> None:
        event: dict = {
            "type": EventType.EMIT_PROGRESS,
            "step": step, "progress": progress,
        }
        if message:
            event["message"] = message
        await self._publish(event)

    # ── business events (step is auto-tagged if emitter is step-bound) ───

    async def storyboard_scene_ready(self, scene_idx: int, scene: dict) -> None:
        await self._publish({
            "type": EventType.STORYBOARD_SCENE_READY,
            "scene_idx": scene_idx, "scene": scene,
        })

    async def shot_frame_ready(
        self,
        scene_idx: int,
        shot_idx: int,
        frame_type: str,
        image_url: str,
    ) -> None:
        await self._publish({
            "type": EventType.SHOT_FRAME_READY,
            "scene_idx": scene_idx,
            "shot_idx": shot_idx,
            "frame_type": frame_type,
            "image_url": image_url,
        })

    async def shot_video_ready(
        self,
        scene_idx: int,
        shot_idx: int,
        video_url: str,
        video_preview_url: str = "",
    ) -> None:
        event = {
            "type": EventType.SHOT_VIDEO_READY,
            "scene_idx": scene_idx,
            "shot_idx": shot_idx,
            "video_url": video_url,
        }
        if video_preview_url:
            event["video_preview_url"] = video_preview_url
        await self._publish(event)

    async def shot_video_preview_ready(
        self,
        scene_idx: int,
        shot_idx: int,
        video_preview_url: str,
    ) -> None:
        await self._publish({
            "type": EventType.SHOT_VIDEO_PREVIEW_READY,
            "scene_idx": scene_idx,
            "shot_idx": shot_idx,
            "video_preview_url": video_preview_url,
        })

    async def scene_composite_ready(
        self,
        scene_idx: int,
        composited_video: str,
        composited_preview: str,
    ) -> None:
        await self._publish({
            "type": EventType.SCENE_COMPOSITE_READY,
            "scene_idx": scene_idx,
            "composited_video": composited_video,
            "composited_preview": composited_preview,
        })

    async def final_video_ready(
        self,
        final_video_url: str,
        final_preview_url: str = "",
    ) -> None:
        event = {
            "type": EventType.FINAL_VIDEO_READY,
            "final_video_url": final_video_url,
        }
        if final_preview_url:
            event["final_preview_url"] = final_preview_url
        await self._publish(event)

    async def portrait_image_status(
        self,
        identifier: str,
        view: str,
        status: str,
        image_url: str | None = None,
    ) -> None:
        event: dict = {
            "type": EventType.PORTRAIT_IMAGE_STATUS,
            "identifier": identifier,
            "view": view,
            "status": status,
        }
        if image_url:
            event["image_url"] = image_url
        await self._publish(event)


class EventBus:
    def __init__(self):
        self._queues: dict[int, list[asyncio.Queue]] = {}

    def subscribe(self, project_id: int) -> asyncio.Queue:
        if project_id not in self._queues:
            self._queues[project_id] = []
        q: asyncio.Queue = asyncio.Queue()
        self._queues[project_id].append(q)
        return q

    def unsubscribe(self, project_id: int, queue: asyncio.Queue):
        if project_id in self._queues:
            self._queues[project_id] = [q for q in self._queues[project_id] if q is not queue]

    async def publish(self, project_id: int, event: dict):
        if project_id not in self._queues:
            return
        alive = []
        for q in self._queues[project_id]:
            try:
                await q.put(event)
                alive.append(q)
            except Exception:
                pass
        self._queues[project_id] = alive


event_bus = EventBus()


def _json_default(obj: Any):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return obj.dict()
        except TypeError:
            pass
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "__str__"):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def sse_encode(event: dict) -> str:
    data = json.dumps(event, ensure_ascii=False, default=_json_default)
    return f"data: {data}\n\n"
