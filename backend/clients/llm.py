"""LLM chat provider with rate-limited queuing.

Usage
-----
.. code-block:: python

    content = await LLM.chat(
        "gpt-4o",
        [SystemMessage(content="You are a helpful assistant."),
         HumanMessage(content="Hello")],
        api_key="sk-...",
        base_url="https://api.openai.com/v1",
        project_id=42,
        task_id="story-gen",
        rpm=500, rpd=2000,
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from backend.clients.errors import NonRetryableError
from backend.clients.rate_limiter import RateLimitConfig, RateQueue

logger = logging.getLogger(__name__)


_ROUTING: dict[str, str | None] = {
    "agnes": "openai",
    "gpt": "openai",
    "gemini": "google_genai",
    "claude": "anthropic",
}

_ENV_KEY_MAP: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

_OPENAI_COMPATIBLE = {None, "openai"}


def _resolve_provider(model: str) -> str | None:
    model_lower = model.lower()
    for key, provider in _ROUTING.items():
        if key in model_lower:
            return provider
    return None


def _create_model(model: str, api_key: str, base_url: str) -> BaseChatModel:
    model_lower = model.lower()
    model_provider = _resolve_provider(model)

    resolved_key = api_key or os.environ.get(_ENV_KEY_MAP.get(model_provider or "", ""), "")

    kwargs: dict[str, Any] = {"model": model}
    if resolved_key:
        kwargs["api_key"] = resolved_key
    if model_provider is not None:
        kwargs["model_provider"] = model_provider
    if model_provider in _OPENAI_COMPATIBLE and base_url:
        kwargs["base_url"] = base_url

    return init_chat_model(**kwargs)


def _resolve_key(model: str) -> str:
    provider = _resolve_provider(model)
    return f"{provider or 'unknown'}:{model}"


_NON_RETRYABLE_NAMES = frozenset({
    "NotFoundError",
    "AuthenticationError",
    "PermissionDeniedError",
    "BadRequestError",
    "UnprocessableEntityError",
})


def _is_non_retryable(e: Exception) -> bool:
    """Check if the exception is a permanent API error that should not be retried."""
    cls_name = type(e).__name__
    if cls_name in _NON_RETRYABLE_NAMES:
        return True
    msg = str(e)
    if "404" in msg and "Not Found" in msg:
        return True
    return False


class LLM:
    _queues: dict[str, RateQueue] = {}
    _models: dict[str, BaseChatModel] = {}
    _default_rpm: int = 50
    _default_rpd: int = 2000

    @classmethod
    def configure(cls, *, rpm: int | None = None, rpd: int | None = None) -> None:
        if rpm is not None:
            cls._default_rpm = rpm
        if rpd is not None:
            cls._default_rpd = rpd

    @classmethod
    async def chat(
        cls,
        model: str,
        messages: list[BaseMessage],
        api_key: str,
        base_url: str,
        *,
        project_id: int = 0,
        task_id: str = "",
        rpm: int | None = None,
        rpd: int | None = None,
        metadata: dict[str, Any] | None = None,
        urgent: bool = False,
        **invoke_kwargs: Any,
    ) -> str:
        """Send a chat message with rate-limited queuing.

        Parameters
        ----------
        rpm, rpd
            If not provided, falls back to class defaults (set via ``configure()``).
        """
        rpm = cls._default_rpm if rpm is None else rpm
        rpd = cls._default_rpd if rpd is None else rpd

        key = _resolve_key(model)
        if key not in cls._queues:
            cls._queues[key] = RateQueue(
                model_key=key,
                config=RateLimitConfig(rpm=rpm, rpd=rpd),
                project_id=project_id,
            )
        queue = cls._queues[key]

        if key not in cls._models:
            cls._models[key] = _create_model(model, api_key, base_url)
        langchain_model = cls._models[key]

        try:
            result = await queue.submit(
                lambda: langchain_model.ainvoke(messages, **invoke_kwargs),
                task_id=task_id,
                metadata=metadata,
                urgent=urgent,
            )
        except Exception as e:
            if _is_non_retryable(e):
                raise NonRetryableError(str(e), original=e) from e
            raise
        return result.content if hasattr(result, "content") else str(result)
