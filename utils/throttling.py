"""Clipsay throttling helpers: async rate limiter + tenacity retry callback.

The :class:`RateLimiter` enforces per-minute and per-day caps on
outbound API requests.  :func:`warn_on_retry` is a tenacity ``after``
callback that logs each retry attempt with the exception type and
attempt number.  :func:`api_retry` is a pre-configured ``@retry``
decorator for the common Clipsay pattern: 3 attempts, log on each
retry, re-raise the original exception.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from typing import Optional

import tenacity
from tenacity import retry, stop_after_attempt


class RateLimiter:
    """Async rate limiter (per-minute and per-day)."""

    def __init__(
        self,
        max_requests_per_minute: Optional[int] = None,
        max_requests_per_day: Optional[int] = None,
    ):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_day = max_requests_per_day
        self.request_times: list[float] = []
        self.lock = asyncio.Lock()

        if max_requests_per_minute and max_requests_per_minute > 0:
            self.min_delay = 60.0 / max_requests_per_minute
        else:
            self.min_delay = 0

    async def acquire(self) -> None:
        """Block until a new request is permitted by the rate limits."""
        if not self.max_requests_per_minute and not self.max_requests_per_day:
            return

        async with self.lock:
            current_time = time.time()

            # Trim the request log to the largest window we care about.
            if self.max_requests_per_day:
                self.request_times = [t for t in self.request_times if current_time - t < 86400]
            elif self.max_requests_per_minute:
                self.request_times = [t for t in self.request_times if current_time - t < 60]

            # Daily cap (coarse).
            if self.max_requests_per_day and self.max_requests_per_day > 0:
                daily_requests = [t for t in self.request_times if current_time - t < 86400]
                if len(daily_requests) >= self.max_requests_per_day:
                    oldest_request = daily_requests[0]
                    wait_time = 86400 - (current_time - oldest_request)
                    if wait_time > 0:
                        hours = wait_time / 3600
                        logging.info(
                            "Daily rate limit reached (%d requests/day). "
                            "Waiting %.1f hours...",
                            self.max_requests_per_day, hours,
                        )
                        await asyncio.sleep(wait_time)
                        current_time = time.time()
                        self.request_times = [
                            t for t in self.request_times if current_time - t < 86400
                        ]

            # Per-minute cap.
            if self.max_requests_per_minute and self.max_requests_per_minute > 0:
                minute_requests = [t for t in self.request_times if current_time - t < 60]
                if len(minute_requests) >= self.max_requests_per_minute:
                    oldest_request = minute_requests[0]
                    wait_time = 60 - (current_time - oldest_request)
                    if wait_time > 0:
                        logging.info(
                            "Rate limit reached (%d requests/min). Waiting %.1fs...",
                            self.max_requests_per_minute, wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        current_time = time.time()
                        if self.max_requests_per_day:
                            self.request_times = [
                                t for t in self.request_times if current_time - t < 86400
                            ]
                        else:
                            self.request_times = [
                                t for t in self.request_times if current_time - t < 60
                            ]

                # Enforce the minimum delay between consecutive requests.
                if self.request_times and self.min_delay > 0:
                    last_request = self.request_times[-1]
                    time_since_last = current_time - last_request
                    if time_since_last < self.min_delay:
                        wait_time = self.min_delay - time_since_last
                        await asyncio.sleep(wait_time)
                        current_time = time.time()

            self.request_times.append(current_time)


def warn_on_retry(retry_state: tenacity.RetryCallState) -> None:
    """Tenacity ``after`` callback that logs a warning before each retry."""
    if retry_state.outcome.failed:
        exc = retry_state.outcome.exception()
        logging.warning(
            "Retrying %s due to %r (attempt %d)",
            getattr(retry_state.fn, "__name__", "<fn>"),
            exc, retry_state.attempt_number,
        )
        logging.debug(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )


def api_retry(stop: int = 3, reraise: bool = True):
    """The standard Clipsay ``@retry`` decorator for outbound API calls.

    Args:
        stop: number of attempts before giving up.
        reraise: when True (default), re-raise the original exception
            after the final attempt.  When False, let tenacity wrap it
            in a :class:`tenacity.RetryError` so the caller can inspect
            the chain.  Set False only when the caller needs to
            intercept the failure (e.g. the i2v->t2v fallback in the
            video generator).
    """
    return retry(
        stop=stop_after_attempt(stop),
        after=warn_on_retry,
        reraise=reraise,
    )
