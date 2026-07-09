"""Agnes image API provider with reference-image resolution and download."""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any

import aiohttp

from backend.clients.base import BaseProvider
from backend.clients.errors import ServerError

logger = logging.getLogger(__name__)


class AgnesImageProvider(BaseProvider):
    """Agnes image API provider with reference-image resolution and download."""

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        refs = payload.pop("reference_images", None)
        save_path = payload.pop("save_path", None)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if refs:
            resolved = await self._resolve_refs(refs)
            extra_body = dict(payload.get("extra_body", {}))
            extra_body["image"] = resolved
            body = {**payload, "model": self.model, "extra_body": extra_body}
        else:
            body = {**payload, "model": self.model}

        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/v1/images/generations"

        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(url, json=body) as resp:
                resp_body = await resp.json(content_type=None)
                self.check_content_filter(
                    resp.status, resp_body, prompt,
                    provider="agnes", model=self.model,
                )
                if resp.status >= 500:
                    raise ServerError(status=resp.status, body=str(resp_body))
                if resp.status >= 400:
                    raise RuntimeError(
                        f"Image generation failed: status={resp.status} body={resp_body}"
                    )

                result_url = self._extract_url(resp_body)
                if save_path and result_url:
                    await self._download(result_url, save_path)

                return resp_body

    @staticmethod
    def _extract_url(data: dict) -> str:
        result = data.get("data", [])
        if result:
            return result[0].get("url", "")
        return ""

    @staticmethod
    async def _resolve_refs(refs: list[dict]) -> list[str]:
        result: list[str] = []
        for ref in refs:
            url = ref.get("url", "")
            path = ref.get("path", "")
            if url:
                result.append(url)
            elif path and os.path.exists(path):
                ext = Path(path).suffix.lower()
                mime = mimetypes.types_map.get(ext, "image/png")
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                result.append(f"data:{mime};base64,{b64}")
            else:
                logger.warning("Reference image not found: url=%s path=%s", url, path)
        return result

    @staticmethod
    async def _download(url: str, save_path: str) -> None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        timeout = aiohttp.ClientTimeout(total=300)
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        with open(save_path, "wb") as f:
                            f.write(await resp.read())
                break
            except Exception as e:
                last_exc = e
                logger.warning(
                    "Image download attempt %d/3 failed: url=%s err=%s: %s",
                    attempt, url, type(e).__name__, e,
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt * 5)  # 10s, 20s
        else:
            logger.error(
                "Image download failed after 3 attempts: url=%s save_path=%s err=%s: %s",
                url, save_path, type(last_exc).__name__, last_exc,
            )
            raise last_exc or RuntimeError(f"Download failed: {save_path}")
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            logger.error("Image download produced empty/missing file: %s", save_path)
            raise RuntimeError(f"Downloaded image is missing or empty: {save_path}")
