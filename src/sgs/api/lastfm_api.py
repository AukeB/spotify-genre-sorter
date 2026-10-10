"""Looks up artist tags on Last.fm, starting from an artist name.

The response is returned as it is, so it can be parsed later. Last.fm reports
most problems in the response body, so the status is taken from that body.
"""

import requests

from sgs.constants import LASTFM_API_URL, LASTFM_MIN_INTERVAL_SECONDS
from sgs.utils.rate_limiter import RateLimiter

_limiter = RateLimiter(LASTFM_MIN_INTERVAL_SECONDS)


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
    """
    _limiter.wait()
    response = requests.get(
        LASTFM_API_URL,
        params={
            "method": "artist.gettoptags",
            "artist": artist_name,
            "api_key": api_key,
            "format": "json",
        },
        timeout=10,
    )

    payload = response.json()
    status = "error" if "error" in payload else "found"
    result = {"status": status, "payload": payload}

    return result
