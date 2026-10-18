"""Looks up artists on MusicBrainz, starting from a Spotify artist ID.

MusicBrainz links artists to their Spotify page with a "free streaming"
relation. That relation is used to find the MusicBrainz artist, whose genres and
tags are then requested. Responses are returned as they are, so they can be
parsed later.
"""

from sgs.api.http import get, retry_api_error
from sgs.constants import (
    APP_USER_AGENT,
    MUSICBRAINZ_MIN_INTERVAL_SECONDS,
    MUSICBRAINZ_URL,
)
from sgs.utils.rate_limiter import RateLimiter

_limiter = RateLimiter(MUSICBRAINZ_MIN_INTERVAL_SECONDS)


def _find_linked_artist_id(url_lookup: dict) -> str | None:
    """Returns the MusicBrainz artist ID linked to a Spotify artist page.

    Args:
        url_lookup (dict): The response of the URL lookup.

    Returns:
        musicbrainz_id (str | None): The linked artist ID, or None if there is
            none.
    """

    musicbrainz_id = None

    for relation in url_lookup.get("relations", []):
        if relation.get("type") == "free streaming" and "artist" in relation:
            musicbrainz_id = relation["artist"]["id"]
            break

    return musicbrainz_id


@retry_api_error
def fetch_musicbrainz_artist(spotify_artist_id: str) -> dict:
    """Looks up one Spotify artist on MusicBrainz, with its genres and tags.

    Args:
        spotify_artist_id (str): The Spotify artist ID.

    Returns:
        result (dict): The status, "found" or "not_matched", and the raw
            "payload" with the URL lookup and the MusicBrainz artist.

    Raises:
        requests.HTTPError: If MusicBrainz returns an error other than 404 for
            the URL lookup, or any error for the artist request.
    """

    headers = {"User-Agent": APP_USER_AGENT}
    spotify_url = f"https://open.spotify.com/artist/{spotify_artist_id}"

    _limiter.wait()

    url_response = get(
        f"{MUSICBRAINZ_URL}/url",
        params={"resource": spotify_url, "inc": "artist-rels", "fmt": "json"},
        headers=headers,
    )

    if url_response.status_code == 404:
        result = {
            "status": "not_matched",
            "payload": {"url_lookup": None, "artist": None},
        }

        return result

    url_response.raise_for_status()
    url_lookup = url_response.json()
    musicbrainz_id = _find_linked_artist_id(url_lookup)

    if musicbrainz_id is None:
        result = {
            "status": "not_matched",
            "payload": {"url_lookup": url_lookup, "artist": None},
        }

        return result

    _limiter.wait()

    artist_response = get(
        f"{MUSICBRAINZ_URL}/artist/{musicbrainz_id}",
        params={"inc": "genres+tags", "fmt": "json"},
        headers=headers,
    )

    artist_response.raise_for_status()
    artist = artist_response.json()

    result = {
        "status": "found",
        "payload": {"url_lookup": url_lookup, "artist": artist},
    }

    return result
