"""Per-model rate limiting with priority queuing, retry, and event notification.

Components
----------
- ``RateLimitConfig`` — static configuration for one model.
- ``TokenBucket`` — async-compatible token bucket for RPM throttling.
- ``DailyCounter`` — persistent daily counter backed by SQLite.
- ``RateQueue`` — per-model async queue with worker pool, priority lanes,
  transient-error retry, and ``TaskNotifier`` integration.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, NamedTuple

import aiosqlite

from backend.clients.errors import (
    AlreadyQueued,
    ContentFilterError,
    DailyLimitExceeded,
    RateLimitError,
    ServerError,
)
from backend.clients.task_notifier import TaskNotifier

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────


@dataclass
class RateLimitConfig:
    max_concurrency: int = 4
    rpm: int = 60
    rpd: int = 2000
    max_retries: int = 3
    retry_backoff_base: int = 2
    retry_backoff_max: int = 60


# ── TokenBucket ──────────────────────────────────────────────────────────


class TokenBucket:
    """Async token bucket for requests-per-minute (RPM) limiting."""

    def __init__(self, capacity: int, refill_per_sec: float | None = None):
        self._capacity = capacity
        self._tokens = float(capacity)
        self._refill = refill_per_sec if refill_per_sec is not None else capacity / 60.0
        self._last_refill = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        while True:
            async with self._lock:
                self._refill_tokens()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / \
                    self._refill if self._refill > 0 else 1.0
            await asyncio.sleep(min(wait, 5.0))

    def _refill_tokens(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens +
                           elapsed * self._refill)
        self._last_refill = now

    def update_capacity(self, capacity: int) -> None:
        """Dynamically update the bucket capacity (RPM)."""
        self._capacity = capacity
        self._refill = capacity / 60.0


# ── DailyCounter ────────────────────────────────────────────────────────


class DailyCounter:
    """Persistent daily request counter backed by SQLite.

    Creates ``rate_limit_daily`` table on first access if it does not exist.
    """

    def __init__(self, model_key: str, max_per_day: int):
        self._model_key = model_key
        self._max = max_per_day
        self._today: str | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _db_path() -> str:
        from backend.db import DB_PATH
        return DB_PATH

    async def _ensure_table(self) -> None:
        async with aiosqlite.connect(self._db_path()) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_daily (
                    model_key TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def can_accept(self) -> bool:
        today = date.today().isoformat()
        await self._ensure_table()
        async with aiosqlite.connect(self._db_path()) as db:
            db.row_factory = aiosqlite.Row
            row = await (await db.execute(
                "SELECT date, count FROM rate_limit_daily WHERE model_key = ?",
                (self._model_key,),
            )).fetchone()
        if row is None or row["date"] != today:
            return True
        return row["count"] < self._max

    async def increment(self) -> None:
        today = date.today().isoformat()
        await self._ensure_table()
        async with aiosqlite.connect(self._db_path()) as db:
            await db.execute("""
                INSERT INTO rate_limit_daily (model_key, date, count)
                VALUES (?, ?, 1)
                ON CONFLICT(model_key) DO UPDATE SET
                    count = CASE WHEN date = ? THEN count + 1 ELSE 1 END,
                    date = ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (self._model_key, today, today, today))
            await db.commit()
        self._today = today

    def update_max(self, max_per_day: int) -> None:
        """Dynamically update the daily limit."""
        self._max = max_per_day


# ── Queued task type ─────────────────────────────────────────────────────


class _QueuedTask(NamedTuple):
    callable: Callable[[], Awaitable[Any]]
    future: asyncio.Future
    task_id: str
    metadata: dict[str, Any] | None


# ── RateQueue ────────────────────────────────────────────────────────────


class RateQueue:
    """Per-model priority queue with rate limiting, retry, and event publishing.

    Usage
    -----
    .. code-block:: python

        queue = RateQueue("openai:gpt-4o", config, project_id=42)
        result = await queue.submit(lambda: api_call(), task_id="my-task")
    """

    def __init__(
        self,
        model_key: str,
        config: RateLimitConfig,
        project_id: int,
        notifier: type[TaskNotifier] = TaskNotifier,
    ):
        self.model_key = model_key
        self.project_id = project_id
        self._config = config
        self._notifier = notifier

        self._normal: asyncio.Queue[_QueuedTask] = asyncio.Queue()
        self._high: asyncio.Queue[_QueuedTask] = asyncio.Queue()
        self._rpm = TokenBucket(config.rpm)
        self._rpd = DailyCounter(model_key, config.rpd)
        self._pending: set[str] = set()

        for _ in range(config.max_concurrency):
            asyncio.create_task(self._worker())

    def update_config(self, rpm: int, rpd: int) -> None:
        """Dynamically update rate limits without recreating the queue."""
        self._config.rpm = rpm
        self._config.rpd = rpd
        self._rpm.update_capacity(rpm)
        self._rpd.update_max(rpd)
        logger.info("[RateQueue] %s config updated: rpm=%d rpd=%d",
                    self.model_key, rpm, rpd)

    async def submit(
        self,
        callable: Callable[[], Awaitable[Any]],
        task_id: str = "",
        metadata: dict[str, Any] | None = None,
        urgent: bool = False,
    ) -> Any:
        if task_id and task_id in self._pending:
            raise AlreadyQueued(task_id)
        if task_id:
            self._pending.add(task_id)

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        task = _QueuedTask(callable, future, task_id, metadata)
        q = self._high if urgent else self._normal
        await q.put(task)

        if task_id:
            await self._notifier.queued(
                self.project_id, task_id, self.model_key,
                self._size(), metadata,
            )

        return await future

    def _size(self) -> int:
        return self._normal.qsize() + self._high.qsize()

    # ── worker ───────────────────────────────────────────────────────

    async def _worker(self) -> None:
        while True:
            task = await self._dequeue()
            try:
                await self._execute(task)
            except Exception as exc:
                logger.exception("RateQueue worker unhandled error")
                if not task.future.done():
                    task.future.set_exception(exc)
            finally:
                self._pending.discard(task.task_id)

    async def _dequeue(self) -> _QueuedTask:
        if not self._high.empty():
            return await self._high.get()
        return await self._normal.get()

    async def _execute(self, task: _QueuedTask) -> None:
        task_id, metadata = task.task_id, task.metadata

        await self._notifier.processing(
            self.project_id, task_id, self.model_key,
            "等待速率配额", metadata,
        )
        await self._rpm.acquire()

        if not await self._rpd.can_accept():
            task.future.set_exception(DailyLimitExceeded(
                self.model_key, self._config.rpd))
            await self._notifier.failed(
                self.project_id, task_id, self.model_key,
                f"日配额({self._config.rpd})耗尽", 1, self._config.max_retries, metadata,
            )
            return

        # Concurrency is bounded by max_concurrency workers (N coroutines).
        await self._notifier.processing(
            self.project_id, task_id, self.model_key,
            "API 调用中", metadata,
        )

        for attempt in range(1, self._config.max_retries + 1):
            try:
                result = await task.callable()
                await self._rpd.increment()
                task.future.set_result(result)
                await self._notifier.completed(
                    self.project_id, task_id, self.model_key, result, metadata,
                )
                return
            except ContentFilterError as e:
                # ContentFilterError is NOT transient — pass through to let
                # the outer layer (Image.generate / Video.generate) rewrite
                # the prompt and retry at the business level.
                task.future.set_exception(e)
                await self._notifier.failed(
                    self.project_id, task_id, self.model_key,
                    "内容审核未通过", attempt, self._config.max_retries, metadata,
                )
                return
            except (RateLimitError, ServerError, TimeoutError, ConnectionError) as e:
                if attempt < self._config.max_retries:
                    delay = min(
                        self._config.retry_backoff_base ** attempt,
                        self._config.retry_backoff_max,
                    )
                    await self._notifier.retrying(
                        self.project_id, task_id, self.model_key,
                        attempt, self._config.max_retries, delay, str(
                            e), metadata,
                    )
                    await asyncio.sleep(delay)
                else:
                    task.future.set_exception(e)
                    await self._notifier.failed(
                        self.project_id, task_id, self.model_key,
                        str(e), attempt, self._config.max_retries, metadata,
                    )
                    return
            except Exception as e:
                task.future.set_exception(e)
                await self._notifier.failed(
                    self.project_id, task_id, self.model_key,
                    str(e), attempt, self._config.max_retries, metadata,
                )
                return
