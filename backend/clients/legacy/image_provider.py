from __future__ import annotations

from typing import Any

from ..base import BaseProvider
from ._http import async_post


class _OpenAIImage(BaseProvider):
    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {**payload, "model": self.model}
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        return await async_post(
            f"{base}/v1/images/generations", headers, body
        )


class _ImagenImage(BaseProvider):
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
        return await async_post(url, headers, body)


class ImageProvider:
    _ROUTING: dict[str, type[BaseProvider]] = {
        "agnes": _OpenAIImage,
        "dall-e": _OpenAIImage,
        "imagen": _ImagenImage,
    }

    @classmethod
    def create(cls, model: str, api_key: str, base_url: str) -> BaseProvider:
        model_lower = model.lower()
        for key, provider_cls in cls._ROUTING.items():
            if key in model_lower:
                return provider_cls(model, api_key, base_url)
        return _OpenAIImage(model, api_key, base_url)
