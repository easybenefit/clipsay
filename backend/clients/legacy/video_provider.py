from __future__ import annotations

from typing import Any

from ..base import BaseProvider
from ._http import async_post
from .agnes_video import AgnesVideoProvider


class _VeoVideo(BaseProvider):
    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {"instances": [{"prompt": prompt}], "model": self.model}
        return await async_post(
            f"{self.base_url}/v1/video/generations", headers, body
        )


class _KlingVideo(BaseProvider):
    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {**payload, "model": self.model}
        return await async_post(
            f"{self.base_url}/v1/videos/generations", headers, body
        )


class VideoProvider:
    _ROUTING: dict[str, type[BaseProvider]] = {
        "agnes": AgnesVideoProvider,
        "veo": _VeoVideo,
        "kling": _KlingVideo,
    }

    @classmethod
    def create(cls, model: str, api_key: str, base_url: str) -> BaseProvider:
        model_lower = model.lower()
        for key, provider_cls in cls._ROUTING.items():
            if key in model_lower:
                return provider_cls(model, api_key, base_url)
        return AgnesVideoProvider(model, api_key, base_url)
