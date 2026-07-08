from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


IMAGE_API_TIMEOUT = 300
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 10.0

_logger = logging.getLogger("_http")


class HTTPError_(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


def _should_retry(status: int) -> bool:
    return status >= 500 or status == 429


def _sync_post(url: str, headers: dict, body: dict, _retries: int = 0) -> dict[str, Any]:
    data = json.dumps(body).encode()
    req = urllib_request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=IMAGE_API_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        status = e.code
        body_text = e.read().decode()
        if _should_retry(status) and _retries < MAX_RETRIES:
            delay = min(BASE_DELAY * (2 ** _retries) + random.uniform(0, 0.5), MAX_DELAY)
            _logger.warning(
                "HTTP %d on %s, retrying %d/%d after %.1fs...",
                status, url, _retries + 1, MAX_RETRIES, delay,
            )
            time.sleep(delay)
            return _sync_post(url, headers, body, _retries=_retries + 1)
        raise HTTPError_(status, body_text) from e
    except URLError as e:
        raise HTTPError_(0, f"Connection failed: {e.reason}") from e


async def async_post(url: str, headers: dict, body: dict) -> dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_post, url, headers, body)
