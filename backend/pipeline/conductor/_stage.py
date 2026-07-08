"""A single pipeline stage backed by ``asyncio.Event``."""

from __future__ import annotations

import asyncio

from backend.pipeline.conductor._types import STAGE_DEFAULT_TIMEOUT, StageKey, StageStatus


class Stage:
    """One checkpoint in the pipeline, identified by a :class:`StageKey`.

    Lifecycle::

        PENDING → CREATING → COMPLETE
        PENDING → STALE → PENDING (recycle)
    """

    __slots__ = ("_event", "_status", "_key")

    def __init__(self, key: StageKey) -> None:
        self._key = key
        self._event = asyncio.Event()
        self._status = StageStatus.PENDING

    # ── read-only properties ──────────────────────────────────────────

    @property
    def key(self) -> StageKey:
        return self._key

    @property
    def status(self) -> StageStatus:
        return self._status

    @property
    def resource(self) -> str:
        return self._key.resource

    @property
    def is_complete(self) -> bool:
        return self._status == StageStatus.COMPLETE

    @property
    def is_staled(self) -> bool:
        return self._status == StageStatus.STALE

    @property
    def identity(self) -> str:
        """Human-readable identifier for logging."""
        return str(self._key)

    # ── state transitions ─────────────────────────────────────────────

    def start(self) -> None:
        """PENDING → CREATING"""
        self._status = StageStatus.CREATING

    def complete(self) -> None:
        """CREATING → COMPLETE (also accepts PENDING → COMPLETE)."""
        self._status = StageStatus.COMPLETE
        self._event.set()

    def stale(self) -> None:
        """Any state → STALE.

        The stage is invalidated and can be recycled back to PENDING
        via :meth:`reset` (e.g. when a frame needs to be regenerated).
        """
        self._status = StageStatus.STALE

    def reset(self) -> None:
        """STALE → PENDING.

        Clears the event so consumers will block again.
        """
        self._status = StageStatus.PENDING
        self._event.clear()

    # ── waiting ───────────────────────────────────────────────────────

    async def wait(self, timeout: float = STAGE_DEFAULT_TIMEOUT) -> None:
        coro = self._event.wait()
        await asyncio.wait_for(coro, timeout=timeout)
