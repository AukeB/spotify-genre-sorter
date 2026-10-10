"""Looks up artist tags on Last.fm, starting from an artist name.

The response is returned as it is, so it can be parsed later. Last.fm reports
most problems in the response body, so the status is taken from that body.
"""

from sgs.api.http import get, retry_api_error
from sgs.errors import LastfmInvalidKeyError, RetryableApiError
from sgs.constants import (
    LASTFM_API_URL,
    LASTFM_MIN_INTERVAL_SECONDS,
    APP_USER_AGENT,
)
from sgs.utils.rate_limiter import RateLimiter

_limiter = RateLimiter(LASTFM_MIN_INTERVAL_SECONDS)

# Last.fm's error code for an API key it does not accept.
LASTFM_INVALID_KEY_CODE = 10
# Last.fm's error code for exceeding its request rate.
LASTFM_RATE_LIMIT_CODE = 29


@retry_api_error
def fetch_lastfm_top_tags(artist_name: str, api_key: str) -> dict:
    """Fetches the top tags Last.fm has for an artist name.

    Args:
        artist_name (str): The artist name, as stored in the cache.
        api_key (str): A Last.fm API key.

    Returns:
        result (dict): The status, "found" or "error", and the raw "payload"
            with the response body.

    Raises:
        requests.HTTPError: If the request itself fails, for example because of
            a network problem or a server error without a Last.fm body.
        LastfmInvalidKeyError: If Last.fm rejects the API key.
    """
    _limiter.wait()
    response = get(
        LASTFM_API_URL,
        params={
            "method": "artist.gettoptags",
            "artist": artist_name,
            "api_key": api_key,
            "format": "json",
        },
        headers={"User-Agent": APP_USER_AGENT},
    )

    payload = response.json()

    if payload.get("error") == LASTFM_RATE_LIMIT_CODE:
        raise RetryableApiError(None)

    if payload.get("error") == LASTFM_INVALID_KEY_CODE:
        raise LastfmInvalidKeyError("Last.fm rejected the API key")

    status = "error" if "error" in payload else "found"
    result = {"status": status, "payload": payload}

    return result
