from __future__ import annotations

import asyncio
import json
import logging
import traceback

from backend.db import (
    get_pipeline_status, update_pipeline_status, update_step_status,
    init_pipeline_steps, reset_downstream_steps,
    update_step_db_status,
)
from backend.db.projects import load_session_config
from backend.pipeline.conductor._types import StageStatus
from backend.clients.errors import NonRetryableError
from backend.pipeline.events import EventBus, EventEmitter, event_bus
from backend.pipeline.config import STEP_NAMES, SessionConfig
from backend.pipeline.step_registry import STEP_EXECUTORS, STEP_DOWNSTREAM

_runner_logger = logging.getLogger("pipeline.runner")
if not _runner_logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(message)s", datefmt="%H:%M:%S"))
    _runner_logger.addHandler(h)
_runner_logger.setLevel(logging.INFO)


class PipelineRunner:
    _instances: dict[int, "PipelineRunner"] = {}

    def __init__(self, project_id: int, bus: EventBus | None = None):
        self.project_id = project_id
        self.bus = bus or event_bus
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._cancel_flag = False
        self._task: asyncio.Task | None = None

    def _emitter(self, step: str = "") -> EventEmitter:
        return EventEmitter.for_step(self.bus, self.project_id, step) if step \
            else EventEmitter(self.bus, self.project_id)

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def start(self, config: SessionConfig, start_step: str | None = None):
        if self._task and not self._task.done():
            raise RuntimeError("Pipeline is already running")
        self._cancel_flag = False
        self._pause_event.set()
        await init_pipeline_steps(self.project_id)
        await update_pipeline_status(self.project_id, "running")
        await self._emitter().pipeline_started()
        self._task = asyncio.create_task(self._run(config, start_step))

    async def pause(self):
        self._pause_event.clear()
        await update_pipeline_status(self.project_id, "paused")
        await self._emitter().pipeline_paused()

    async def resume(self):
        self._pause_event.set()
        await update_pipeline_status(self.project_id, "running")
        await self._emitter().pipeline_resumed()
        # If task is done (completed/failed), start a new one
        if self._task and self._task.done():
            cfg = await load_session_config(self.project_id)
            self._task = asyncio.create_task(self._run(cfg))

    async def cancel(self):
        self._cancel_flag = True
        self._pause_event.set()
        await update_pipeline_status(self.project_id, "cancelled")
        await self._emitter().pipeline_cancelled()

    async def regenerate_step(self, step: str, config: SessionConfig | None = None):
        if self._task and not self._task.done():
            raise RuntimeError("Pipeline is running; cancel or wait first")
        self._cancel_flag = False
        self._pause_event.set()
        await reset_downstream_steps(self.project_id, step)
        await update_pipeline_status(self.project_id, "running", step=step)
        await self._emitter().pipeline_started()
        cfg = config or await load_session_config(self.project_id)
        self._task = asyncio.create_task(self._run(cfg, start_step=step))

    def is_running(self) -> bool:
        return bool(self._task and not self._task.done())

    async def get_status(self) -> dict:
        return await get_pipeline_status(self.project_id)

    @classmethod
    def get_for_project(cls, project_id: int) -> "PipelineRunner":
        if project_id not in cls._instances:
            cls._instances[project_id] = cls(project_id)
        return cls._instances[project_id]

    @classmethod
    def remove(cls, project_id: int):
        cls._instances.pop(project_id, None)

    # ── internal ─────────────────────────────────────────────────────────────

    async def _run(self, config: SessionConfig, start_step: str | None = None):
        try:
            await self._run_impl(config, start_step)
        except asyncio.CancelledError:
            _runner_logger.info(
                "[runner] pipeline cancelled for project_id=%d", self.project_id)
            pass
        except Exception as e:
            tb = traceback.format_exc()
            _runner_logger.error(
                "[runner] pipeline failed for project_id=%d: %s\n%s",
                self.project_id, e, tb,
            )
            await update_pipeline_status(
                self.project_id, "failed", error=f"{type(e).__name__}: {e}")
            await self._emitter().pipeline_failed(error=f"{type(e).__name__}: {e}")

    async def _run_impl(self, config: SessionConfig, start_step: str | None = None):
        status = await get_pipeline_status(self.project_id)

        start_idx = 0
        if start_step and start_step in STEP_NAMES:
            start_idx = STEP_NAMES.index(start_step)

        for idx, step_name in enumerate(STEP_NAMES):
            if idx < start_idx:
                continue

            if self._cancel_flag:
                return

            # check pause before each step
            await self._pause_event.wait()
            if self._cancel_flag:
                return

            # skip completed steps (only if restarting after pause)
            s = await get_pipeline_status(self.project_id)
            if s.get("pipeline_status") == "completed" and idx > start_idx:
                continue

            await self._emitter().step_start(step_name)
            _runner_logger.info(
                "[runner] project_id=%d entering step=%s (idx=%d)",
                self.project_id, step_name, idx,
            )
            await update_pipeline_status(self.project_id, "running", step=step_name)
            await update_step_status(self.project_id, step_name, "running")
            await update_step_db_status(self.project_id, step_name, StageStatus.CREATING)

            emit = self._emitter(step_name)
            pause_check = self._make_pause_check()

            max_retries = 5
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    executor = STEP_EXECUTORS.get(step_name)
                    if not executor:
                        raise ValueError(f"No executor for step: {step_name}")

                    _runner_logger.info(
                        "[runner] project_id=%d step=%s attempt=%d invoking",
                        self.project_id, step_name, attempt,
                    )
                    if step_name in ("shot_frames", "storyboard"):
                        result = await executor(config, emit, pause_check)
                    else:
                        result = await executor(config, emit)
                    _runner_logger.info(
                        "[runner] project_id=%d step=%s attempt=%d succeeded: %s",
                        self.project_id, step_name, attempt, type(
                            result).__name__,
                    )

                    await update_step_status(
                        self.project_id, step_name, "completed")
                    await update_step_db_status(
                        self.project_id, step_name, StageStatus.COMPLETE)
                    await self._emitter().step_complete(step_name, result)
                    await self._emitter().project_data_changed()
                    last_exception = None
                    break
                except NonRetryableError as e:
                    tb = traceback.format_exc()
                    _runner_logger.error(
                        "[runner] project_id=%d step=%s non-retryable error: %s\n%s",
                        self.project_id, step_name, e, tb,
                    )
                    last_exception = e
                    break
                except Exception as e:
                    tb = traceback.format_exc()
                    _runner_logger.error(
                        "[runner] project_id=%d step=%s attempt=%d failed: %s\n%s",
                        self.project_id, step_name, attempt, e, tb,
                    )
                    last_exception = e
                    if attempt < max_retries:
                        backoff = min(2 ** (attempt + 1), 120)
                        _runner_logger.info(
                            "[runner] project_id=%d step=%s retrying in %ds (attempt %d/%d)",
                            self.project_id, step_name, backoff, attempt, max_retries,
                        )
                        await self._emitter().step_retry(
                            step_name, attempt, max_retries, str(e),
                        )
                        await asyncio.sleep(backoff)

            if last_exception:
                await update_step_status(
                    self.project_id, step_name, "failed",
                    error=str(last_exception))
                await update_step_db_status(
                    self.project_id, step_name, StageStatus.STALE)
                await update_pipeline_status(
                    self.project_id, "paused", step=step_name,
                    error=str(last_exception))
                await self._emitter().step_failed(step_name, str(last_exception))
                await self._emitter().pipeline_paused(
                    reason=f"Step '{step_name}' failed after {max_retries} attempts",
                    error=str(last_exception),
                )
                self._pause_event.clear()
                return

        await update_pipeline_status(self.project_id, "completed")
        await self._emitter().pipeline_completed()

    def _make_pause_check(self):
        async def check():
            await self._pause_event.wait()
            if self._cancel_flag:
                raise asyncio.CancelledError("Pipeline cancelled")
        return check
