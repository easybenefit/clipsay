"""Video generation provider with rate-limited queuing and content-filter rewrite.

Usage
-----
.. code-block:: python

    result, final_prompt = await Video.generate(
        "agnes-video-v2.0",
        {"prompt": "a cat walking", ...},
        api_key="sk-...",
        base_url="https://apihub.agnes-ai.com/v1",
        project_id=42,
        task_id="s1-shot3-video",
        rpm=50, rpd=1000,
        on_filter=handle_rewrite,
    )
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from backend.clients.base import BaseProvider
from backend.clients.errors import ContentFilterError
from backend.clients.providers.agnes_video import AgnesTaskFailed, AgnesVideoProvider
from backend.clients.rate_limiter import RateLimitConfig, RateQueue
from backend.utils.sanitizer import sanitizer

logger = logging.getLogger(__name__)


# ── Low-level provider implementations ───────────────────────────────────


class _VeoVideo(BaseProvider):
    """Google Veo API."""

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {"instances": [{"prompt": prompt}], "model": self.model}
        url = f"{self.base_url}/v1/video/generations"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=body) as resp:
                resp_body = await resp.json(content_type=None)
                self.check_content_filter(resp.status, resp_body, prompt, "veo", self.model)
                if resp.status >= 400:
                    raise RuntimeError(f"Veo failed: {resp.status} {resp_body}")
                return resp_body


class _KlingVideo(BaseProvider):
    """Kling API."""

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {**payload, "model": self.model}
        url = f"{self.base_url}/v1/videos/generations"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=body) as resp:
                resp_body = await resp.json(content_type=None)
                self.check_content_filter(resp.status, resp_body, payload.get("prompt", ""), "kling", self.model)
                if resp.status >= 400:
                    raise RuntimeError(f"Kling failed: {resp.status} {resp_body}")
                return resp_body


# ── Routing ──────────────────────────────────────────────────────────────


_ROUTING: dict[str, type[BaseProvider]] = {
    "agnes": AgnesVideoProvider,
    "veo": _VeoVideo,
    "kling": _KlingVideo,
}


def _resolve(model: str) -> str:
    model_lower = model.lower()
    for key in _ROUTING:
        if key in model_lower:
            return key
    return "agnes"


def _create(model: str, api_key: str, base_url: str) -> BaseProvider:
    model_lower = model.lower()
    for key, provider_cls in _ROUTING.items():
        if key in model_lower:
            return provider_cls(model, api_key, base_url)
    return AgnesVideoProvider(model, api_key, base_url)


# ── Public API ───────────────────────────────────────────────────────────


class Video:
    _queues: dict[str, RateQueue] = {}
    _default_rpm: int = 1
    _default_rpd: int = 1000

    @classmethod
    def configure(cls, *, rpm: int | None = None, rpd: int | None = None) -> None:
        if rpm is not None:
            cls._default_rpm = rpm
        if rpd is not None:
            cls._default_rpd = rpd

    @classmethod
    async def generate(
        cls,
        model: str,
        payload: dict[str, Any],
        api_key: str,
        base_url: str,
        *,
        project_id: int = 0,
        task_id: str = "",
        rpm: int | None = None,
        rpd: int | None = None,
        max_retries_content_filter: int = 3,
        metadata: dict[str, Any] | None = None,
        urgent: bool = False,
        on_filter: Callable[[ContentFilterError], Awaitable[str]] | None = None,
    ) -> tuple[Any, str]:
        """Generate a video with rate-limited queuing and optional content-filter rewrite.

        Parameters
        ----------
        rpm, rpd
            If not provided, falls back to class defaults (set via ``configure()``).
        """
        rpm = cls._default_rpm if rpm is None else rpm
        rpd = cls._default_rpd if rpd is None else rpd

        prompt = sanitizer.sanitize(payload.get("prompt", ""))
        payload = {**payload, "prompt": prompt}

        key = f"{_resolve(model)}:{model}"
        if key not in cls._queues:
            cls._queues[key] = RateQueue(
                model_key=key,
                config=RateLimitConfig(rpm=rpm, rpd=rpd),
                project_id=project_id,
            )
        queue = cls._queues[key]
        provider = _create(model, api_key, base_url)

        for attempt in range(max_retries_content_filter):
            try:
                result = await queue.submit(
                    lambda: provider.invoke(payload),
                    task_id=task_id,
                    metadata=metadata,
                    urgent=urgent,
                )
                return result, prompt
            except ContentFilterError:
                if attempt == max_retries_content_filter - 1 or not on_filter:
                    raise
                new_prompt = await on_filter(ContentFilterError(
                    prompt=prompt,
                    reason="content_filter",
                    provider=_resolve(model),
                    model=model,
                ))
                prompt = sanitizer.sanitize(new_prompt)
                payload = {**payload, "prompt": prompt}
        raise RuntimeError("Content filter retry exhausted")
