"""Lightweight pub/sub event bus for pipeline stage transitions.

External consumers (e.g. SSE handlers) subscribe to resource transitions
and are notified whenever a stage changes state.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Dict, List

from backend.pipeline.conductor._types import StageStatus

logger = logging.getLogger("coordinator.bus")


class EventBus:
    """Publish-subscribe channel for stage lifecycle events."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[..., Awaitable[None]]]] = {}

    def on(self, resource: str,
           handler: Callable[..., Awaitable[None]]) -> None:
        """Register *handler* to be called when *resource* transitions."""
        self._listeners.setdefault(resource, []).append(handler)

    def off(self, resource: str,
            handler: Callable[..., Awaitable[None]]) -> None:
        """Remove a previously registered handler."""
        self._listeners[resource].remove(handler)

    async def emit(
        self,
        resource: str,
        project_id: int,
        scene_idx: int,
        status: StageStatus,
        shot_id: int | None = None,
        **payload: Any,
    ) -> None:
        """Notify all subscribers of *resource* about a state transition."""
        for handler in list(self._listeners.get(resource, [])):
            try:
                await handler(
                    project_id=project_id,
                    scene_idx=scene_idx,
                    shot_id=shot_id,
                    name=resource,
                    status=status,
                    **payload,
                )
            except Exception:
                logger.exception(
                    "Listener %s failed for resource=%s (%d, %d)",
                    handler.__name__, resource, project_id, scene_idx,
                )
