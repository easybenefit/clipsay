import logging

logger = logging.getLogger("retry")


def log_retry_failure(retry_state) -> None:
    logger.warning(
        "Retry attempt %s failed: %s",
        retry_state.attempt_number,
        retry_state.outcome.exception() if retry_state.outcome else "unknown",
    )
