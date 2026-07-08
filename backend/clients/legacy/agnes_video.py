"""Agnes AI video generator.

Endpoint: POST https://apihub.agnes-ai.com/v1/videos
Status:   GET  https://apihub.agnes-ai.com/v1/videos/{task_id}

The API is async-only: a single POST submits a task, the server returns
``task_id``, and the caller polls until ``status == SUCCESS``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..base import BaseProvider

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SEC = 5
_MAX_POLL_ATTEMPTS = 120
_INVALID_IMAGE_MARKERS = ("Invalid image",)
_USER_AGENT = "Clipsay/1.0"


class _AgnesTaskFailed(Exception):
    def __init__(self, task_id: str, reason):
        super().__init__(reason)
        self.task_id = task_id


class AgnesVideoProvider(BaseProvider):
    def __init__(self, model: str, api_key: str, base_url: str):
        super().__init__(model, api_key, base_url)
        self.poll_interval = _POLL_INTERVAL_SEC
        self.max_poll_attempts = _MAX_POLL_ATTEMPTS

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
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

    async def _submit_and_poll(self, payload: dict) -> dict[str, Any]:
        import aiohttp

        async with aiohttp.ClientSession(headers=self._headers()) as session:
            async with session.post(
                f"{self.base_url}/videos",
                json=payload,
            ) as resp:
                create_body = await resp.json(content_type=None)
                if resp.status >= 400:
                    raise RuntimeError(
                        f"Agnes video create failed: status={resp.status} body={create_body}"
                    )
                task_id = create_body.get("id")
                if not task_id:
                    raise RuntimeError(
                        f"Agnes video create returned no task_id: {create_body}"
                    )

            for attempt in range(1, self.max_poll_attempts + 1):
                await asyncio.sleep(self.poll_interval)
                async with session.get(
                    f"{self.base_url}/videos/{task_id}",
                ) as poll_resp:
                    poll_body = await poll_resp.json(content_type=None)
                if poll_resp.status >= 400:
                    logger.warning(
                        "Agnes poll attempt %d/%d: status=%s body=%s",
                        attempt, self.max_poll_attempts, poll_resp.status, poll_body,
                    )
                    continue
                status = (poll_body or {}).get("status", "")
                progress = (poll_body or {}).get("progress", "")
                logger.info(
                    "Agnes task %s: status=%s progress=%s (attempt %d/%d)",
                    task_id, status, progress, attempt, self.max_poll_attempts,
                )
                status_upper = status.upper()
                if status_upper == "FAILED":
                    fail_reason = poll_body.get("fail_reason") or poll_body.get("error") or str(poll_body)
                    raise _AgnesTaskFailed(task_id, fail_reason)
                if status_upper in ("COMPLETED", "SUCCESS"):
                    result_url = (
                        poll_body.get("remixed_from_video_id")
                        or poll_body.get("video_url")
                        or poll_body.get("url")
                        or poll_body.get("result_url")
                    )
                    if not result_url:
                        raise RuntimeError(
                            f"Agnes task {task_id} succeeded but no result URL: {poll_body}"
                        )
                    return {"data": [{"url": result_url}]}

        raise TimeoutError(
            f"Agnes task {task_id} did not complete within "
            f"{self.max_poll_attempts * self.poll_interval}s"
        )

    async def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = payload.get("prompt", "")
        extra = payload.get("extra_body", {})
        ref_images = extra.get("image", [])
        if isinstance(ref_images, str):
            ref_images = [ref_images]

        valid_urls = [p for p in ref_images if p.startswith(("http://", "https://", "data:"))]
        is_i2v = len(valid_urls) > 0

        agnes_payload = self._build_payload(payload)
        try:
            return await self._submit_and_poll(agnes_payload)
        except _AgnesTaskFailed as exc:
            reason = str(exc)
            if not is_i2v:
                raise RuntimeError(reason) from exc
            if not any(marker in reason for marker in _INVALID_IMAGE_MARKERS):
                raise RuntimeError(reason) from exc
            logger.warning(
                "Agnes i2v task %s failed image validation (%s); falling back to t2v",
                exc.task_id, reason[:120],
            )
            fallback = self._build_payload({"prompt": prompt, "extra_body": {}})
            return await self._submit_and_poll(fallback)
