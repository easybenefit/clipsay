from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.clients.errors import ContentFilterError


class BaseProvider(ABC):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @abstractmethod
    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    async def stream(self, payload: dict[str, Any]):
        raise NotImplementedError("Streaming not supported")
        yield  # pragma: no cover

    # ── Content filter detection helpers ─────────────────────────────

    _FILTER_KEYWORDS = (
        "content_filter", "safety", "inappropriate",
        "敏感词", "安全", "review", "blocked", "nsfw",
    )

    @classmethod
    def check_content_filter(
        cls,
        status: int,
        body: dict[str, Any],
        prompt: str,
        provider: str = "",
        model: str = "",
    ) -> None:
        """Raise ``ContentFilterError`` if the response indicates a content-
        safety rejection.  Call this from ``invoke()`` before raising generic
        errors."""
        error = body.get("error", body)
        if isinstance(error, dict):
            err_code = (error.get("code", "") or "").lower()
            err_msg = (error.get("message", "") or str(body)).lower()
        else:
            err_code = ""
            err_msg = str(error).lower()

        if status in (400, 403):
            if any(kw in err_code for kw in cls._FILTER_KEYWORDS):
                raise ContentFilterError(prompt, str(body), provider, model, err_code)
            if any(kw in err_msg for kw in cls._FILTER_KEYWORDS):
                raise ContentFilterError(prompt, str(body), provider, model, "content_filter")

    @classmethod
    def check_video_fail_reason(cls, reason: str, prompt: str, provider: str = "", model: str = "") -> None:
        """Check a video task failure reason for content-safety flags."""
        if any(kw in reason.lower() for kw in cls._FILTER_KEYWORDS):
            raise ContentFilterError(prompt, reason, provider, model, "video_safety")
