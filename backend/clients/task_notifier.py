"""Publishes ``task_status`` events to EventBus for real-time frontend updates.

All methods are static -- the class holds no state. Each method builds a
structured event dict and pushes it to the global ``event_bus``.

``event_bus`` is imported lazily inside each method to avoid circular imports
(``backend.pipeline.events`` → ``backend.pipeline.runner`` → ``backend.db``).
"""

from __future__ import annotations

from typing import Any


def _get_event_bus():
    from backend.pipeline.events import event_bus
    return event_bus


class TaskNotifier:

    @staticmethod
    async def queued(
        project_id: int,
        task_id: str,
        model_key: str,
        queue_size: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await _get_event_bus().publish(project_id, {
            "type": "task_status",
            "task_id": task_id,
            "model": model_key,
            "status": "queued",
            "message": f"排队中（前方{queue_size}个）",
        })

    @staticmethod
    async def processing(
        project_id: int,
        task_id: str,
        model_key: str,
        message: str,
        metadata: dict[str, Any] | None = None,
        attempt: int = 1,
    ) -> None:
        await _get_event_bus().publish(project_id, {
            "type": "task_status",
            "task_id": task_id,
            "model": model_key,
            "status": "processing",
            "message": message,
            "attempt": attempt,
        })

    @staticmethod
    async def retrying(
        project_id: int,
        task_id: str,
        model_key: str,
        attempt: int,
        max_retries: int,
        retry_delay: int,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await _get_event_bus().publish(project_id, {
            "type": "task_status",
            "task_id": task_id,
            "model": model_key,
            "status": "retrying",
            "message": f"{error}，{retry_delay}s 后第 {attempt+1}/{max_retries} 次重试",
            "attempt": attempt,
            "max_retries": max_retries,
            "retry_delay": retry_delay,
        })

    @staticmethod
    async def completed(
        project_id: int,
        task_id: str,
        model_key: str,
        result: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await _get_event_bus().publish(project_id, {
            "type": "task_status",
            "task_id": task_id,
            "model": model_key,
            "status": "completed",
            "result": result,
        })

    @staticmethod
    async def failed(
        project_id: int,
        task_id: str,
        model_key: str,
        error: str,
        attempt: int = 1,
        max_retries: int = 3,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await _get_event_bus().publish(project_id, {
            "type": "task_status",
            "task_id": task_id,
            "model": model_key,
            "status": "failed",
            "message": error,
            "attempt": attempt,
            "max_retries": max_retries,
        })
