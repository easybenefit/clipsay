"""Clipsay image generator backed by the Agnes AI API.

Endpoint: POST https://apihub.agnes-ai.com/v1/images/generations
Available models (verified via probe):
  - agnes-image-2.1-flash  (recommended; newer)
  - agnes-image-2.0-flash  (previous generation)

Supported sizes (verified): 1024x1024, 1024x1792, 1792x1024, 512x512.

Two non-obvious behaviors that the probe uncovered:

1. **GCS download requires a User-Agent header.**  The returned ``url``
   points at ``storage.googleapis.com/agnes-aigc-test/...``.  When
   fetched with ``aiohttp``'s default empty User-Agent the GCS bucket
   returns ``<Error><Code>AuthenticationRequired</Code></Error>`` (a
   131-byte XML payload that is *not* a PNG).  We always pass a
   User-Agent on both the generation call and the image-download call.

2. **i2i degrades gracefully.**  The OpenAI-style
   ``/v1/images/edits`` endpoint is not currently exposed by Agnes.
   When ``reference_image_paths`` is non-empty we first try posting
   the references as base64 in the ``image`` field of
   ``/v1/images/generations``; if that returns 4xx we fall back to t2i
   with a warning so the pipeline keeps moving.

The class returns :class:`ImageOutput` with ``fmt="pil"`` (rather than
``fmt="url"``) so that :meth:`ImageOutput.save` doesn't trigger a
second UA-less ``requests.get`` via
:func:`utils.image_io.download_image` (which would fail).
"""

from __future__ import annotations

import base64
import io
import logging
import re
from math import gcd
from typing import List, Optional

import aiohttp
from PIL import Image

from schemas.image_output import ImageOutput
from utils.throttling import RateLimiter, api_retry
from utils.user_agent import _USER_AGENT

# Sizes confirmed working against the live API.  Any caller-supplied
# size outside this set is coerced to the closest matching aspect
# ratio or the default.
_ALLOWED_SIZES = ("1024x1024", "1024x1792", "1792x1024", "512x512")
_DEFAULT_SIZE = "1024x1024"
_DEFAULT_MODEL = "agnes-image-2.1-flash"

# 16:9 / 9:16 / 1:1 aspect ratio → Agnes fixed size.  Agnes doesn't
# accept arbitrary aspect ratios, so we map common calls (e.g.
# ``shot_orchestrator`` passing ``size="1600x900"``) to the nearest
# valid fixed size.
_ASPECT_TO_SIZE = {
    "16:9": "1792x1024",
    "9:16": "1024x1792",
    "1:1": "1024x1024",
    "4:3": "1024x1024",
    "3:4": "1024x1024",
}


def _reference_to_payload_value(path: str) -> str:
    """Return the value to send in the request's ``image`` field.

    The OpenAI-compatible ``image`` field accepts either a remote URL
    or a base64-encoded local file.  Callers may legitimately pass
    either, so we detect URLs and pass them through; only local files
    get base64-encoded.
    """
    if path.startswith(("http://", "https://")):
        return path
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _aspect_from_size_string(size: str) -> Optional[str]:
    """Map a ``"WxH"`` string to a canonical aspect-ratio key.

    Returns ``None`` if the input isn't a ``WxH`` string.  Examples::

        "1600x900"   -> "16:9"
        "1280x720"   -> "16:9"
        "1920x1080"  -> "16:9"
        "1024x1024"  -> "1:1"
    """
    m = re.match(r"^\s*(\d+)\s*[xX*]\s*(\d+)\s*$", size or "")
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        return None
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def _resolve_size(size: Optional[str], aspect_ratio: Optional[str]) -> str:
    """Pick a size that Agnes will actually accept.

    Priority: explicit ``size`` (when valid) > ``aspect_ratio`` mapping >
    aspect ratio inferred from the supplied size > default.

    Invalid sizes are coerced to the closest valid size that **matches
    the requested aspect ratio** rather than always falling back to
    the square default.  This matters for the video pipeline: callers
    like ``shot_orchestrator`` pass ``size="1600x900"`` (a 16:9 still),
    and falling back to ``1024x1024`` would silently change the aspect
    ratio of the first frame from landscape to square.
    """
    if size and size in _ALLOWED_SIZES:
        return size

    if size:
        requested_aspect = _aspect_from_size_string(size)
        mapped = _ASPECT_TO_SIZE.get(requested_aspect) if requested_aspect else None
        if mapped is not None:
            logging.warning(
                "Agnes image generator: size %r is not in the supported set %s; "
                "falling back to %s (matched aspect ratio %r)",
                size, _ALLOWED_SIZES, mapped, requested_aspect,
            )
            return mapped
        logging.warning(
            "Agnes image generator: size %r is not in the supported set %s "
            "and its aspect ratio %r is unknown; falling back to default %s "
            "(this may change the image's aspect ratio)",
            size, _ALLOWED_SIZES, requested_aspect, _DEFAULT_SIZE,
        )
        return _DEFAULT_SIZE

    if aspect_ratio:
        mapped = _ASPECT_TO_SIZE.get(aspect_ratio)
        if mapped:
            return mapped
        logging.warning(
            "Agnes image generator: unknown aspect_ratio %r; "
            "falling back to default %s",
            aspect_ratio, _DEFAULT_SIZE,
        )

    return _DEFAULT_SIZE


class AgnesImageGenerator:
    """Image generator backed by the Agnes AI API."""

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.api_key = api_key
        self.base_url = "https://apihub.agnes-ai.com/v1/images/generations"
        self.model = model
        self.rate_limiter = rate_limiter

    @api_retry(stop=3)
    async def generate_single_image(
        self,
        prompt: str,
        reference_image_paths: List[str] = None,
        size: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        **kwargs,
    ) -> ImageOutput:
        """Generate a single image.

        Args:
            prompt: text prompt.
            reference_image_paths: optional list of local image paths used as
                references.  Best-effort: sent as base64 in the ``image``
                field of the request.  If Agnes rejects the i2v call
                (4xx), falls back to text-only with a warning.
            size: explicit WxH.  Must be one of
                ``{1024x1024, 1024x1792, 1792x1024, 512x512}`` or a
                size with a recognised aspect ratio.
            aspect_ratio: convenience alias for ``size`` (e.g.
                ``"16:9"``).

        Returns:
            ``ImageOutput(fmt="pil", ext="png", data=<PIL.Image>)``.  We
            download the GCS-hosted URL with a User-Agent and decode
            to PIL inline so that :meth:`ImageOutput.save` never
            re-fetches the image with a UA-less ``requests.get`` (which
            GCS rejects).
        """
        if reference_image_paths is None:
            reference_image_paths = []
        resolved_size = _resolve_size(size, aspect_ratio)

        if self.rate_limiter:
            await self.rate_limiter.acquire()

        logging.info("Calling %s (size=%s) to generate image...", self.model, resolved_size)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": resolved_size,
        }
        if reference_image_paths:
            payload["image"] = [
                _reference_to_payload_value(path)
                for path in reference_image_paths
            ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.base_url, json=payload) as response:
                    response_json = await response.json(content_type=None)
        except Exception as e:
            logging.error("Error occurred while generating image: %s", e)
            raise

        # If the i2i attempt is rejected, fall back to t2i with a warning.
        if reference_image_paths and response_json.get("error"):
            err = response_json["error"]
            logging.warning(
                "Agnes image generator: i2i call rejected (%s: %s); "
                "falling back to text-only with the original prompt",
                err.get("type"), err.get("message"),
            )
            fallback_payload = {k: v for k, v in payload.items() if k != "image"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.base_url, json=fallback_payload) as response:
                    response_json = await response.json(content_type=None)

        try:
            url = response_json["data"][0]["url"]
        except (KeyError, IndexError, TypeError) as e:
            logging.error("Unexpected Agnes image response: %s", response_json)
            raise ValueError(f"Agnes image generator: no image url in response: {e}")

        # Download with User-Agent — GCS rejects empty UA.  Decode to
        # PIL so the caller never re-fetches the URL via
        # utils.image_io.download_image.
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": _USER_AGENT}) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    blob = await response.read()
        except Exception as e:
            logging.error("Failed to download generated image from %s: %s", url[:120], e)
            raise

        try:
            pil_image = Image.open(io.BytesIO(blob))
            pil_image.load()  # force decode now so failures surface here
        except Exception as e:
            logging.error("Failed to decode downloaded image: %s", e)
            raise

        return ImageOutput(fmt="pil", ext="png", data=pil_image, source_url=url)
