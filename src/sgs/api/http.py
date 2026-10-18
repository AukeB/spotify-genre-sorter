"""Shared HTTP helper for the API clients.

Every request goes through get(), so a rate limit is always reported the same
way: as RetryableApiError. Functions decorated with retry_api_error are tried
again after such an error, or after a timeout or dropped connection, with the
waits set in constants.py.
"""

import requests

from sgs.constants import (
    RATE_LIMIT_BACKOFF,
    RATE_LIMIT_BASE_DELAY_SECONDS,
    RATE_LIMIT_MAX_ATTEMPTS,
    RATE_LIMIT_MAX_DELAY_SECONDS,
    RETRYABLE_ERROR_CODES,
)
from sgs.errors import RetryableApiError
from sgs.utils.retry import retry

retry_api_error = retry(
    (RetryableApiError, requests.Timeout, requests.ConnectionError),
    max_attempts=RATE_LIMIT_MAX_ATTEMPTS,
    base_delay=RATE_LIMIT_BASE_DELAY_SECONDS,
    backoff=RATE_LIMIT_BACKOFF,
    max_delay=RATE_LIMIT_MAX_DELAY_SECONDS,
)


def _retry_after_seconds(response: requests.Response) -> float | None:
    """Reads the Retry-After header as a number of seconds.

    Args:
        response (requests.Response): A response with status 429.

    Returns:
        retry_after (float | None): Seconds to wait, or None if the header is
            missing or is not a number of seconds.
    """

    header = response.headers.get("Retry-After")
    retry_after: float | None = None

    if header is not None:
        try:
            retry_after = float(header)
        except ValueError:
            retry_after = None

    return retry_after


def get(
    url: str, headers: dict[str, str], params: dict[str, str] | None = None
) -> requests.Response:
    """Sends a GET request, reporting HTTP 429 as RetryableApiError.

    Other status codes are returned as they are, so callers decide what they
    mean.

    Args:
        url (str): The URL to request.
        headers (dict[str, str]): Request headers.
        params (dict[str, str] | None): Query parameters.

    Returns:
        response (requests.Response): The response.

    Raises:
        RetryableApiError: If the response has status 429.
    """

    response = requests.get(url, headers=headers, params=params, timeout=10)

    if response.status_code in RETRYABLE_ERROR_CODES:
        retry_after = _retry_after_seconds(response)

        raise RetryableApiError(retry_after, status_code=response.status_code)

    return response
