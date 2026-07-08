"""Agnes video API provider (submit task → poll → download)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import aiohttp

from backend.clients.base import BaseProvider
from backend.clients.errors import ContentFilterError, RateLimitError

logger = logging.getLogger(__name__)


class AgnesTaskFailed(Exception):
    def __init__(self, task_id: str, reason: Any):
        super().__init__(reason)
        self.task_id = task_id


class AgnesVideoProvider(BaseProvider):
    """Async task-based Agnes video API (submit → poll → download).

    Video generation is serialised: only one task runs at a time via a
    class-level semaphore, on top of the RPM/RPD rate limiter managed by
    :class:`~backend.clients.rate_limiter.RateQueue`.
    """

    _POLL_INTERVAL = 5
    _MAX_POLL_ATTEMPTS = 120
    _INVALID_IMAGE_MARKERS = ("Invalid image",)
    _serial_lock: asyncio.Semaphore | None = None

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Clipsay/1.0",
        }

    def _build_payload(self, body: dict) -> dict:
        prompt = body.get("prompt", "")
        extra = body.get("extra_body", {})
        ref_images = extra.get("image", [])
        if isinstance(ref_images, str):
            ref_images = [ref_images]

        valid_urls = [p for p in ref_images if p.startswith(("http://", "https://", "data:"))]
        has_images = len(valid_urls) > 0

        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "duration": 5,
            "seconds": "5",
        }

        if "size" in extra:
            payload["size"] = extra["size"]
        if "aspect_ratio" in body:
            payload["aspect_ratio"] = body["aspect_ratio"]

        if has_images:
            payload["image"] = valid_urls[0]
        if len(valid_urls) > 1:
            payload["extra_body"] = {
                "image": valid_urls,
                "mode": "keyframes",
            }
        return payload

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Only one video at a time — serialise on top of the RateQueue limiter.
        if self._serial_lock is None:
            self._serial_lock = asyncio.Semaphore(1)
        async with self._serial_lock:
            return await self._do_invoke(payload)

    async def _do_invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        extra = payload.get("extra_body", {})
        save_path = payload.pop("save_path", None)
        ref_images = extra.get("image", [])
        if isinstance(ref_images, str):
            ref_images = [ref_images]
        valid_urls = [p for p in ref_images if p.startswith(("http://", "https://", "data:"))]
        is_i2v = len(valid_urls) > 0

        agnes_payload = self._build_payload(payload)
        try:
            result = await self._submit_and_poll(agnes_payload, prompt)
        except AgnesTaskFailed as exc:
            reason = str(exc)
            if not is_i2v:
                raise RuntimeError(reason) from exc
            if not any(marker in reason for marker in self._INVALID_IMAGE_MARKERS):
                raise RuntimeError(reason) from exc
            logger.warning(
                "Agnes i2v task %s failed image validation; falling back to t2v",
                exc.task_id,
            )
            fallback = self._build_payload({"prompt": prompt, "extra_body": {}})
            result = await self._submit_and_poll(fallback, prompt)

        result_url = self._extract_url(result)
        if save_path and result_url:
            await self._download(result_url, save_path)
        return result

    @staticmethod
    def _extract_url(data: dict) -> str:
        result = data.get("data", [])
        if result:
            return result[0].get("url", "")
        return ""

    @staticmethod
    async def _download(url: str, save_path: str) -> None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        timeout = aiohttp.ClientTimeout(total=120)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    with open(save_path, "wb") as f:
                        f.write(await resp.read())
        except Exception as e:
            logger.error(
                "Video download failed: url=%s save_path=%s err=%s: %s",
                url, save_path, type(e).__name__, e,
            )
            raise
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            logger.error("Video download produced empty/missing file: %s", save_path)
            raise RuntimeError(f"Downloaded video is missing or empty: {save_path}")

    async def _submit_and_poll(self, payload: dict, prompt: str) -> dict[str, Any]:
        async with aiohttp.ClientSession(headers=self._headers()) as session:
            async with session.post(
                f"{self.base_url}/videos",
                json=payload,
            ) as resp:
                create_body = await resp.json(content_type=None)
                if resp.status >= 400:
                    if resp.status == 429:
                        raise RateLimitError(
                            status=resp.status,
                            body=str(create_body),
                        )
                    raise RuntimeError(
                        f"Video create failed: status={resp.status} body={create_body}"
                    )
                task_id = create_body.get("id")
                if not task_id:
                    raise RuntimeError(f"No task_id in create response: {create_body}")

            for attempt in range(1, self._MAX_POLL_ATTEMPTS + 1):
                await asyncio.sleep(self._POLL_INTERVAL)
                async with session.get(f"{self.base_url}/videos/{task_id}") as poll_resp:
                    poll_body = await poll_resp.json(content_type=None)
                if poll_resp.status >= 400:
                    continue

                status = (poll_body or {}).get("status", "").upper()
                if status == "FAILED":
                    fail_reason = (
                        poll_body.get("fail_reason")
                        or poll_body.get("error")
                        or str(poll_body)
                    )
                    self.check_video_fail_reason(fail_reason, prompt, "agnes", self.model)
                    raise AgnesTaskFailed(task_id, fail_reason)

                if status in ("COMPLETED", "SUCCESS"):
                    result_url = (
                        poll_body.get("remixed_from_video_id")
                        or poll_body.get("video_url")
                        or poll_body.get("url")
                        or poll_body.get("result_url")
                    )
                    if not result_url:
                        raise RuntimeError(f"Task {task_id} succeeded but no URL: {poll_body}")
                    return {"data": [{"url": result_url}]}

            raise TimeoutError(
                f"Task {task_id} did not complete within "
                f"{self._MAX_POLL_ATTEMPTS * self._POLL_INTERVAL}s"
            )
