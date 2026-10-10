"""Explores what MusicBrainz and Last.fm return for artists from the cache.

Takes a few random artists from the cache database, then for each one:
- looks up the Spotify artist URL on MusicBrainz, then fetches the matched
  MusicBrainz artist with genres and tags
- looks up the artist name on Last.fm for its top tags

Both responses are logged in full so their shape can be inspected. Nothing is
written to the cache.

Usage:
    uv run python scripts/explore_genre_sources.py --limit 5
    uv run python scripts/explore_genre_sources.py --limit 5 --lastfm-api-key YOUR_KEY
"""

import argparse
import json
import logging
import sqlite3
import time
from pathlib import Path

import requests

from sgs.constants import CACHE_DB_PATH

logger = logging.getLogger(__name__)

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2"
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
USER_AGENT = "SpotifyGenreSorter/0.1 (personal project; exploration script)"
MUSICBRAINZ_DELAY_SECONDS = 1.0
LASTFM_DELAY_SECONDS = 0.25


def _random_artists(db_path: Path, limit: int) -> list[tuple[str, str]]:
    """Returns random artists from the cache as (artist_id, name) pairs.

    Args:
        db_path (Path): Location of the cache file.
        limit (int): How many artists to return.

    Returns:
        artists (list[tuple[str, str]]): The Spotify artist ID and name of each artist.
    """
    connection = sqlite3.connect(db_path)
    rows = connection.execute(
        "SELECT artist_id, name FROM artists ORDER BY RANDOM() LIMIT ?",
        (limit,),
    ).fetchall()
    connection.close()

    artists = [(row[0], row[1]) for row in rows]

    return artists


def _musicbrainz_lookup(spotify_artist_id: str) -> dict:
    """Finds the MusicBrainz artist linked to a Spotify artist, then fetches genres and tags.

    Args:
        spotify_artist_id (str): The Spotify artist ID.

    Returns:
        result (dict): The raw URL lookup and artist responses, or the HTTP status
            if a request failed.
    """
    headers = {"User-Agent": USER_AGENT}
    spotify_url = f"https://open.spotify.com/artist/{spotify_artist_id}"

    url_response = requests.get(
        f"{MUSICBRAINZ_URL}/url",
        params={"resource": spotify_url, "inc": "artist-rels", "fmt": "json"},
        headers=headers,
        timeout=10,
    )
    result = {"url_status": url_response.status_code}

    if url_response.status_code != 200:
        return result

    url_body = url_response.json()
    result["url_lookup"] = url_body
    time.sleep(MUSICBRAINZ_DELAY_SECONDS)

    musicbrainz_id = None

    for relation in url_body.get("relations", []):
        if relation.get("type") == "free streaming" and "artist" in relation:
            musicbrainz_id = relation["artist"]["id"]
            break

    if musicbrainz_id is None:
        result["matched"] = False
        return result

    artist_response = requests.get(
        f"{MUSICBRAINZ_URL}/artist/{musicbrainz_id}",
        params={"inc": "genres+tags", "fmt": "json"},
        headers=headers,
        timeout=10,
    )
    result["artist_status"] = artist_response.status_code
    result["artist"] = artist_response.json()
    time.sleep(MUSICBRAINZ_DELAY_SECONDS)

    return result


def _lastfm_lookup(artist_name: str, api_key: str) -> dict:
    """Fetches the top tags Last.fm has for an artist name.

    Args:
        artist_name (str): The artist name, as stored in the cache.
        api_key (str): A Last.fm API key.

    Returns:
        response (dict): The raw Last.fm response body.
    """
    response = requests.get(
        LASTFM_URL,
        params={
            "method": "artist.gettoptags",
            "artist": artist_name,
            "api_key": api_key,
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    body = response.json()
    time.sleep(LASTFM_DELAY_SECONDS)

    return body


def main() -> None:
    """Samples artists from the cache and logs what each source returns."""
    parser = argparse.ArgumentParser(description="Explore MusicBrainz and Last.fm responses.")
    parser.add_argument("--limit", type=int, default=5, help="How many artists to sample.")
    parser.add_argument("--db", type=Path, default=CACHE_DB_PATH, help="Cache database file.")
    parser.add_argument("--lastfm-api-key", default=None, help="Last.fm API key. Skips Last.fm when not given.")
    args = parser.parse_args()

    artists = _random_artists(args.db, args.limit)
    api_key = args.lastfm_api_key

    if api_key is None:
        logger.info("No --lastfm-api-key given, Last.fm lookups are skipped")

    for spotify_artist_id, name in artists:
        logger.info("=== %s (%s) ===", name, spotify_artist_id)

        musicbrainz_result = _musicbrainz_lookup(spotify_artist_id)
        logger.info("MusicBrainz: %s", json.dumps(musicbrainz_result, indent=2))

        if api_key is not None:
            lastfm_result = _lastfm_lookup(name, api_key)
            logger.info("Last.fm: %s", json.dumps(lastfm_result, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
