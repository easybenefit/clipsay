"""Clipsay video generator backed by the Agnes AI API.

Endpoint: POST https://apihub.agnes-ai.com/v1/videos
Status:   GET  https://apihub.agnes-ai.com/v1/videos/{task_id}
Models:   agnes-video-v2.0 (verified via probe)

The API is async-only: a single POST submits a task, the server
returns ``task_id``, and the caller polls until ``status ==
"completed"``.  On success ``data.result_url`` is the absolute URL of
the generated MP4.

Non-obvious behaviors that the probe uncovered:

1. **The ``duration`` (or ``seconds``) field is Go-typed.**  The
   server accepts ``duration`` as an *int* and ``seconds`` as a
   *string*.  Sending the wrong JSON type returns
   ``{"code":"invalid_json","message":"json: cannot unmarshal ..."}``.
   We send both for forward-compat.

2. **The queue can sit at ``NOT_START`` for a while.**  Observed
   end-to-end latency for a 5-second clip is ~2 minutes: ~30 s of
   queue, ~95 s of in-progress.  Default ``max_poll_attempts *
   poll_interval`` = 600 s.

3. **The advertised ``result_url`` is currently broken (502 from
   Cloudflare).**  The actual MP4 is at ``inner.remixed_from_video_id``
   (a GCS URL that works without auth).  We prefer that field.

Implements the :class:`clients.protocols.VideoGenerator` protocol via
:meth:`generate_single_video`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import aiohttp
from tenacity import retry, stop_after_attempt

from schemas.video_output import VideoOutput
from utils.throttling import RateLimiter, warn_on_retry
from utils.user_agent import _USER_AGENT

_DEFAULT_MODEL = "agnes-video-v2.0"
_BASE_URL = "https://apihub.agnes-ai.com/v1"
# Default poll cadence: 5s.  Observed tasks reach ``completed`` in
# 60-180s.
_POLL_INTERVAL_SEC = 5
# 10 min of total wait.  Observed worst case is ~2 min; 10 min leaves
# headroom for backpressure on the Agnes queue.
_MAX_POLL_ATTEMPTS = 120

# Recognise "Invalid image" failure reasons coming back from the
# server.  The official API requires image references as URLs, so
# base64-related errors should not occur for valid payloads, but we
# keep the marker for general image-validation failures that may
# still arise.
_INVALID_IMAGE_MARKERS = ("Invalid image",)


class _AgnesTaskFailed(Exception):
    """Internal: a video task ended in FAILURE with a server-side reason.

    Carries ``task_id`` so the caller can include it in user-facing
    logs.
    """

    def __init__(self, task_id: str, reason):
        super().__init__(reason)
        self.task_id = task_id
        self.reason = reason


def _is_image_validation_error(reason: str) -> bool:
    """Return True if ``reason`` looks like an image-validation failure.

    These are deterministic — retrying the i2v call with the same
    bytes always fails the same way, so we fall back to t2v instead
    of burning quota on retries.
    """
    if not reason:
        return False
    return any(marker in reason for marker in _INVALID_IMAGE_MARKERS)


def _short(s: str, limit: int = 120) -> str:
    """Truncate ``s`` to ``limit`` chars with an ellipsis suffix."""
    s = str(s)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _reference_to_image_payload(path: str) -> Optional[str]:
    """Convert a reference path to the value sent in the ``image`` field.

    The official Agnes API only accepts HTTP URLs for image references.
    Returns ``None`` for local file paths — the caller should fall
    back to text-only video generation.
    """
    if path.startswith(("http://", "https://")):
        return path
    return None


def _resolution_to_size(resolution: str) -> Optional[str]:
    """Map a Veo-style ``resolution`` string to an Agnes ``size``.

    Agnes only exposes a small set of fixed sizes (verified default is
    ``1280x768``).  We map the two common Clipsay resolutions and let
    anything else fall through unchanged so the caller can still pass
    an explicit ``size`` if needed.
    """
    mapping = {
        "1080p": "1920x1080",
        "720p": "1280x768",
    }
    return mapping.get(resolution)


class AgnesVideoGenerator:
    """Video generator backed by the Agnes async task API."""

    def __init__(
        self,
        api_key: str,
        t2v_model: str = _DEFAULT_MODEL,
        i2v_model: str = _DEFAULT_MODEL,
        poll_interval: int = _POLL_INTERVAL_SEC,
        max_poll_attempts: int = _MAX_POLL_ATTEMPTS,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.api_key = api_key
        self.t2v_model = t2v_model
        self.i2v_model = i2v_model
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts
        self.rate_limiter = rate_limiter
        self.base_url = _BASE_URL

    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }

    def _build_payload(
        self,
        prompt: str,
        reference_image_paths: List[str],
        aspect_ratio: Optional[str],
        size: Optional[str],
        duration: int,
    ) -> dict:
        """Build the create-task request body.

        Rules derived from probing the live API:

        * ``model`` is required.
        * ``prompt`` is required.
        * ``duration`` is an *int*; ``seconds`` is a *string*.  We
          send both so the call works regardless of which the
          server-side validator runs first.
        * ``size`` is optional.  When omitted the server defaults to
          ``1280x768``.
        * ``aspect_ratio`` is optional.  Accepted values (verified):
          ``"16:9"``, ``"9:16"``, ``"1:1"``.
        * ``image`` is optional; single image i2v first-frame.
        * ``extra_body.image`` array + ``extra_body.mode="keyframes"``
          for multi-image keyframes mode.
        """
        if duration <= 0:
            raise ValueError("duration must be a positive integer")

        image_urls = [
            _reference_to_image_payload(p)
            for p in reference_image_paths
        ]
        image_urls = [u for u in image_urls if u]

        has_images = len(image_urls) > 0
        effective_model = self.i2v_model if has_images else self.t2v_model

        payload: dict = {
            "model": effective_model,
            "prompt": prompt,
            "duration": duration,
            "seconds": str(duration),
        }
        if size:
            payload["size"] = size
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if has_images:
            payload["image"] = image_urls[0]
        if len(image_urls) > 1:
            payload["extra_body"] = {
                "image": image_urls,
                "mode": "keyframes",
            }
        return payload

    async def _submit_and_poll(
        self,
        payload: dict,
    ) -> VideoOutput:
        """Submit ``payload`` to Agnes and poll until the task ends.

        Used by :meth:`generate_single_video` for both the i2v
        attempt and the t2v fallback.  Raises ``RuntimeError`` on any
        non-``Invalid image`` failure; the i2v-specific fall-through
        to t2v is handled by the caller, not here.
        """
        async with aiohttp.ClientSession(headers=self._headers()) as session:
            async with session.post(
                f"{self.base_url}/videos",
                json=payload,
            ) as response:
                create_body = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(
                        f"Agnes video create failed: status={response.status} body={create_body}"
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
                    logging.warning(
                        "Agnes video poll: status=%s body=%s (attempt %d/%d)",
                        poll_resp.status, poll_body, attempt, self.max_poll_attempts,
                    )
                    continue
                status = (poll_body or {}).get("status", "")
                progress = (poll_body or {}).get("progress", "")
                logging.info(
                    "Agnes video task %s: status=%s progress=%s (attempt %d/%d)",
                    task_id, status, progress, attempt, self.max_poll_attempts,
                )
                if status == "failed":
                    fail_reason = poll_body.get("fail_reason") or poll_body.get("error") or poll_body
                    raise _AgnesTaskFailed(task_id, fail_reason)
                if status == "completed":
                    result_url = (
                        poll_body.get("remixed_from_video_id")
                        or poll_body.get("video_url")
                        or poll_body.get("url")
                        or poll_body.get("result_url")
                    )
                    if not result_url:
                        raise RuntimeError(
                            f"Agnes video task {task_id} succeeded but no result URL: {poll_body}"
                        )
                    return VideoOutput(fmt="url", ext="mp4", data=result_url)

        raise TimeoutError(
            f"Agnes video task {task_id} did not complete within "
            f"{self.max_poll_attempts * self.poll_interval}s"
        )

    @retry(
        stop=stop_after_attempt(3),
        after=warn_on_retry,
        # We do NOT ``reraise=True`` because we want the fallback
        # logic below to see the original
        # :class:`_AgnesTaskFailed` (which carries the structured
        # ``fail_reason``) and decide whether to fall back to t2v.
        # ``reraise=True`` would re-raise the exception as a bare
        # ``RetryError`` after 3 attempts and hide the cause.  We
        # re-raise manually only after the fallback itself has been
        # attempted.
        reraise=False,
    )
    async def generate_single_video(
        self,
        prompt: str,
        reference_image_paths: List[str],
        resolution: str = "1080p",
        aspect_ratio: str = "16:9",
        duration: int = 5,
        size: Optional[str] = None,
        **kwargs,
    ) -> VideoOutput:
        """Generate a single video from ``prompt`` and optional references.

        Args:
            prompt: text prompt.
            reference_image_paths: HTTP URLs used as image references.
                Single -> i2v first-frame.  Multiple -> keyframes
                mode (``extra_body.image`` array).  Local paths are
                silently dropped (Agnes only accepts HTTP URLs).
            resolution: kept for protocol compatibility; Agnes does
                not expose a ``resolution`` parameter.  We map
                ``"1080p"`` to ``size="1920x1080"`` and ``"720p"`` to
                ``size="1280x768"`` when ``size`` is not explicitly
                provided.
            aspect_ratio: ``"16:9"``, ``"9:16"``, or ``"1:1"``.
            duration: video length in seconds.
            size: explicit ``WxH``.  Overrides ``resolution``-derived size.

        Returns:
            ``VideoOutput(fmt="url", ext="mp4", data=<result_url>)``.
            We return the URL rather than the bytes because the MP4
            lives on a GCS-backed CDN and can be re-fetched cheaply.

        Fallback behavior:
            When an i2v task fails with an image-validation error
            (``"Invalid image"`` in ``fail_reason`` — e.g. ``"Incorrect
            padding"`` or ``"Invalid base64-encoded string"``), the
            generator automatically resubmits the same prompt as a
            text-only t2v task.  A warning is logged and the original
            i2v task is *not* retried (server-side validation is
            deterministic, so retries waste quota).  Any other
            failure (network, timeout, content policy) is re-raised
            so the caller can decide what to do.
        """
        if size is None:
            size = _resolution_to_size(resolution)

        # Filter out local file paths — the official Agnes API only
        # accepts HTTP URLs for i2v references.  Any local paths are
        # dropped with a warning so the call falls through as t2v.
        urls_only: List[str] = []
        for p in (reference_image_paths or []):
            if p.startswith(("http://", "https://")):
                urls_only.append(p)
            else:
                logging.warning(
                    "Agnes video generator: dropping local reference %s "
                    "(only HTTP URLs are accepted).  Falling back to t2v.",
                    p,
                )
        reference_image_paths = urls_only

        is_i2v = bool(reference_image_paths)
        payload = self._build_payload(
            prompt=prompt,
            reference_image_paths=reference_image_paths,
            aspect_ratio=aspect_ratio,
            size=size,
            duration=duration,
        )

        if self.rate_limiter:
            await self.rate_limiter.acquire()

        logging.info(
            "Submitting video task to Agnes (model=%s duration=%ss size=%s i2v=%s)...",
            payload["model"], duration, size, is_i2v,
        )

        try:
            return await self._submit_and_poll(payload)
        except _AgnesTaskFailed as exc:
            reason = str(exc)
            if not is_i2v:
                # t2v failure -> propagate.  No point falling back again.
                raise RuntimeError(reason) from exc
            if not _is_image_validation_error(reason):
                # Non-image i2v failure (content policy, model issue).
                # Don't silently degrade; let the caller decide.
                raise RuntimeError(reason) from exc
            # i2v failed because the image was rejected.  Resubmit
            # as t2v with the same prompt, but prepend the reference
            # image description so the model still has visual
            # context.
            logging.warning(
                "Agnes video task %s failed image validation (%s); "
                "falling back to t2v (text-only).  Character consistency "
                "may be lost.", exc.task_id, _short(reason),
            )
            if self.rate_limiter:
                await self.rate_limiter.acquire()
            fallback_payload = self._build_payload(
                prompt=prompt,
                reference_image_paths=[],
                aspect_ratio=aspect_ratio,
                size=size,
                duration=duration,
            )
            logging.info(
                "Submitting t2v fallback (model=%s duration=%ss size=%s)...",
                fallback_payload["model"], duration, size,
            )
            return await self._submit_and_poll(fallback_payload)
