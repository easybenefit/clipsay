"""Error types for provider invocations and rate limiting."""


class ContentFilterError(Exception):
    """Image/video API rejected the request due to content safety review.

    Unlike transient errors (429/5xx), retrying the same prompt will
    always fail. The prompt must be rewritten by an LLM.
    """

    def __init__(
        self,
        prompt: str,
        reason: str,
        provider: str = "",
        model: str = "",
        code: str = "content_filter",
    ):
        self.prompt = prompt
        self.reason = reason
        self.provider = provider
        self.model = model
        self.code = code
        super().__init__(f"[{provider}] content filter rejected: {reason[:200]}")


class RateLimitError(Exception):
    """HTTP 429 — rate limit exceeded. Retriable by RateQueue."""

    def __init__(self, status: int = 429, body: str = "", retry_after: float | None = None):
        self.status = status
        self.body = body
        self.retry_after = retry_after
        super().__init__(f"HTTP {status}: {body[:200]}")


class ServerError(Exception):
    """HTTP 5xx — server error. Retriable by RateQueue."""

    def __init__(self, status: int, body: str = ""):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body[:200]}")


class DailyLimitExceeded(Exception):
    """Daily quota (rateLimitDay) exhausted."""

    def __init__(self, model_key: str, max_per_day: int):
        self.model_key = model_key
        self.max_per_day = max_per_day
        super().__init__(f"Daily limit {max_per_day} exceeded for {model_key}")


class AlreadyQueued(Exception):
    """Task with the same task_id is already in the queue or running."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task {task_id} is already queued or running")


class NonRetryableError(Exception):
    """A permanent error that should NOT be retried (e.g. 404 model not found,
    401 auth failure, 400 bad request).  Retrying will always produce the same
    result.  The pipeline runner skips retry on this exception."""

    def __init__(self, message: str, code: str = "", original: Exception | None = None):
        self.code = code
        self.original = original
        super().__init__(message)
