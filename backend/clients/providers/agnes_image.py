"""Agnes image API provider with reference-image resolution and download."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

import aiohttp

from backend.clients.base import BaseProvider
from backend.clients.errors import ServerError
from backend.utils.logging import setup_logger

logger = setup_logger("agnes_image")

# API-native exact pixel dimensions for each (ratio, tier) combination.
# From https://agnes-ai.com/zh-Hans/docs/agnes-image-21-flash#输出尺寸参考
_AGNES_NATIVE_SIZES: dict[tuple[str, str], str] = {
    ("1:1", "1K"): "1024x1024", ("1:1", "2K"): "2048x2048",
    ("1:1", "3K"): "3072x3072", ("1:1", "4K"): "4096x4096",
    ("3:4", "1K"): "864x1152",  ("3:4", "2K"): "1728x2304",
    ("3:4", "3K"): "2592x3456", ("3:4", "4K"): "3456x4608",
    ("4:3", "1K"): "1152x864",  ("4:3", "2K"): "2304x1728",
    ("4:3", "3K"): "3456x2592", ("4:3", "4K"): "4608x3456",
    ("16:9", "1K"): "1312x736", ("16:9", "2K"): "2624x1472",
    ("16:9", "3K"): "3936x2208", ("16:9", "4K"): "5248x2944",
    ("9:16", "1K"): "736x1312", ("9:16", "2K"): "1472x2624",
    ("9:16", "3K"): "2208x3936", ("9:16", "4K"): "2944x5248",
    ("2:3", "1K"): "832x1248",  ("2:3", "2K"): "1664x2496",
    ("2:3", "3K"): "2496x3744", ("2:3", "4K"): "3328x4992",
    ("3:2", "1K"): "1248x832",  ("3:2", "2K"): "2496x1664",
    ("3:2", "3K"): "3744x2496", ("3:2", "4K"): "4992x3328",
    ("21:9", "1K"): "1568x672", ("21:9", "2K"): "3136x1344",
    ("21:9", "3K"): "4704x2016", ("21:9", "4K"): "6272x2688",
}


class AgnesImageProvider(BaseProvider):
    """Agnes image API provider with reference-image resolution and download."""

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        refs = payload.get("reference_images")
        save_path = payload.get("save_path")

        logger.info("[AgnesImage] invoke model=%s refs=%d save_path=%s",
                    self.model, len(refs) if refs else 0, save_path or "NONE")
        logger.debug("[AgnesImage] prompt (first 150): %s", prompt[:150])

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {**payload, "model": self.model}
        body.pop("save_path", None)
        self._normalize_size(body)

        if refs:
            resolved = await self._resolve_refs(refs)
            logger.info("[AgnesImage] refs resolved: %d urls", len(resolved))
            extra_body = dict(body.get("extra_body", {}))
            extra_body["image"] = resolved
            body["extra_body"] = extra_body

        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        url = f"{base}/v1/images/generations"

        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.post(url, json=body) as resp:
                resp_body = await resp.json(content_type=None)
                logger.info("[AgnesImage] response status=%d body_keys=%s",
                            resp.status, list(resp_body.keys()) if isinstance(resp_body, dict) else "N/A")

                logger.info("[AgnesImage] response body = %s", resp_body)
                self.check_content_filter(
                    resp.status, resp_body, prompt,
                    provider="agnes", model=self.model,
                )
                if resp.status >= 500:
                    logger.error(
                        "[AgnesImage] server error status=%d body=%s", resp.status, resp_body)
                    raise ServerError(status=resp.status, body=str(resp_body))
                if resp.status >= 400:
                    logger.error(
                        "[AgnesImage] client error status=%d body=%s", resp.status, resp_body)
                    raise RuntimeError(
                        f"Image generation failed: status={resp.status} body={resp_body}"
                    )

                result_url = self._extract_url(resp_body)
                logger.info("[AgnesImage] result_url=%s", result_url if result_url and len(
                    result_url) else result_url or "EMPTY")

                if save_path and result_url:
                    await self._download(result_url, save_path)
                    logger.info("[AgnesImage] saved to %s", save_path)

                return resp_body

    @staticmethod
    def _normalize_size(body: dict[str, Any]) -> None:
        """Convert pixel-format size + ratio to the API's native exact pixel size.

        The Agnes API supports exact pixel dimensions like ``1312x736`` natively.
        By resolving to a native size here, we avoid depending on the ``ratio``
        parameter — which may not be honoured in image-to-image (``extra_body.image``)
        mode.
        """
        size = body.get("size", "")
        ratio = body.get("ratio", "")
        if not ratio or "x" not in size:
            return
        try:
            w = int(size.split("x")[0])
            if w >= 3500:
                tier = "4K"
            elif w >= 2400:
                tier = "3K"
            elif w >= 1300:
                tier = "2K"
            else:
                tier = "1K"
            native = _AGNES_NATIVE_SIZES.get((ratio, tier))
            if native:
                body["size"] = native
                body.pop("ratio", None)
                logger.info(
                    "[AgnesImage] size normalized: %s+%s -> %s", size, ratio, native,
                )
        except (ValueError, IndexError):
            pass

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
                logger.warning(
                    "Reference image not found: url=%s path=%s", url, path)
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
                            logger.info("====>download: %s", save_path)
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
            logger.error(
                "Image download produced empty/missing file: %s", save_path)
            raise RuntimeError(
                f"Downloaded image is missing or empty: {save_path}")
