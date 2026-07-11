"""Image generation provider with rate-limited queuing and content-filter rewrite.

Usage
-----
.. code-block:: python

    result, final_prompt = await Image.generate(
        "agnes-image-2.1-flash",
        {"prompt": "a cat", "n": 1, "size": "1024x576"},
        api_key="sk-...",
        base_url="https://apihub.agnes-ai.com/v1",
        project_id=42,
        task_id="s1-shot3-start",
        rpm=10, rpd=500,
        on_filter=handle_rewrite,
    )
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

from backend.clients.base import BaseProvider
from backend.clients.errors import ContentFilterError
from backend.clients.providers.agnes_image import AgnesImageProvider
from backend.clients.rate_limiter import RateLimitConfig, RateQueue
from backend.clients.task_notifier import TaskNotifier
from backend.utils.sanitizer import sanitizer

logger = logging.getLogger(__name__)


# ── Low-level provider implementations ───────────────────────────────────


class _OpenAIImage(BaseProvider):
    """OpenAI-compatible image API (Agnes, DALL-E)."""

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {**payload, "model": self.model}
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/v1/images/generations"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=body) as resp:
                resp_body = await resp.json(content_type=None)
                self.check_content_filter(
                    resp.status, resp_body, payload.get("prompt", ""),
                    provider="openai", model=self.model,
                )
                if resp.status >= 400:
                    raise RuntimeError(
                        f"Image generation failed: status={resp.status} body={resp_body}"
                    )
                return resp_body


class _ImagenImage(BaseProvider):
    """Google Imagen API."""

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        headers = {"Content-Type": "application/json"}
        url = (
            f"{self.base_url}/v1beta/models/"
            f"{self.model}:predict?key={self.api_key}"
        )
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": payload.get("n", 1)},
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=body) as resp:
                resp_body = await resp.json(content_type=None)
                self.check_content_filter(
                    resp.status, resp_body, prompt,
                    provider="imagen", model=self.model,
                )
                if resp.status >= 400:
                    raise RuntimeError(
                        f"Imagen generation failed: status={resp.status} body={resp_body}"
                    )
                return resp_body


# ── Routing ──────────────────────────────────────────────────────────────


_ROUTING: dict[str, type[BaseProvider]] = {
    "agnes": AgnesImageProvider,
    "dall-e": _OpenAIImage,
    "imagen": _ImagenImage,
}


def _resolve(model: str) -> str:
    model_lower = model.lower()
    for key in _ROUTING:
        if key in model_lower:
            return key
    return "openai"


def _create(model: str, api_key: str, base_url: str) -> BaseProvider:
    model_lower = model.lower()
    for key, provider_cls in _ROUTING.items():
        if key in model_lower:
            return provider_cls(model, api_key, base_url)
    return _OpenAIImage(model, api_key, base_url)


# ── Public API ───────────────────────────────────────────────────────────


class Image:
    _queues: dict[str, RateQueue] = {}
    _model_defaults: dict[str, RateLimitConfig] = {}  # model_key → config

    @classmethod
    def update_rate_limits(cls, model: str, rpm: int, rpd: int) -> None:
        """Set per-model default limits AND update any existing queue."""
        config = RateLimitConfig(rpm=rpm, rpd=rpd)
        cls._model_defaults[model] = config
        updated = 0
        for key, queue in cls._queues.items():
            if model not in key:
                continue
            queue.update_config(rpm, rpd)
            updated += 1
        logger.info("[Image] rate limits set: model=%s rpm=%d rpd=%d queues=%d",
                     model, rpm, rpd, updated)

    @classmethod
    def apply_defaults(cls, defaults: dict[str, tuple[int, int]]) -> None:
        """批量设置多个模型的默认限流值（应用启动时调用）。"""
        for model, (rpm, rpd) in defaults.items():
            cls._model_defaults[model] = RateLimitConfig(rpm=rpm, rpd=rpd)
        logger.info("[Image] defaults applied: %d models", len(defaults))

    @classmethod
    def _resolve_limits(cls, model: str, rpm: int | None, rpd: int | None) -> tuple[int, int]:
        """按优先级：参数 > 模型默认 > 硬编码兜底。"""
        if rpm is not None and rpd is not None:
            return rpm, rpd
        for key, cfg in cls._model_defaults.items():
            if key in model:
                if rpm is None:
                    rpm = cfg.rpm
                if rpd is None:
                    rpd = cfg.rpd
                break
        return rpm or 10, rpd or 500

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
        """Generate an image with rate-limited queue and optional content-filter rewrite.

        Parameters
        ----------
        rpm, rpd
            If not provided, falls back to per-model defaults (see ``update_rate_limits``).
        """
        rpm, rpd = cls._resolve_limits(model, rpm, rpd)

        prompt = sanitizer.sanitize(payload.get("prompt", ""))
        payload = {**payload, "prompt": prompt}

        key = f"{_resolve(model)}:{model}"
        if key not in cls._queues:
            cls._queues[key] = RateQueue(
                model_key=key,
                config=RateLimitConfig(rpm=rpm, rpd=rpd, max_concurrency=2),
                project_id=project_id,
            )
        queue = cls._queues[key]
        provider = _create(model, api_key, base_url)

        logger.info("[Image.generate] model=%s task_id=%s project_id=%d prompt_len=%d size=%s",
                    model, task_id or "N/A", project_id, len(prompt),
                    payload.get("size", "N/A"))
        if "reference_images" in payload:
            logger.info("[Image.generate] reference_images=%d", len(payload["reference_images"]))

        for attempt in range(max_retries_content_filter):
            try:
                result = await queue.submit(
                    lambda: provider.invoke(payload),
                    task_id=task_id,
                    metadata=metadata,
                    urgent=urgent,
                )
                logger.info("[Image.generate] SUCCESS attempt=%d task_id=%s",
                            attempt + 1, task_id or "N/A")
                return result, prompt
            except ContentFilterError as cf_err:
                logger.warning("[Image.generate] ContentFilterError attempt=%d/%d task_id=%s prompt_len=%d",
                               attempt + 1, max_retries_content_filter, task_id or "N/A", len(prompt))
                if attempt == max_retries_content_filter - 1 or not on_filter:
                    logger.error("[Image.generate] ContentFilterError retries exhausted")
                    raise
                new_prompt = await on_filter(ContentFilterError(
                    prompt=prompt,
                    reason="content_filter",
                    provider=_resolve(model),
                    model=model,
                ))
                prompt = sanitizer.sanitize(new_prompt)
                payload = {**payload, "prompt": prompt}
                logger.info("[Image.generate] ContentFilterError retry with new prompt len=%d", len(prompt))
        raise RuntimeError("Content filter retry exhausted")
