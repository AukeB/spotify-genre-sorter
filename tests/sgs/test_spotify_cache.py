"""Module for testing spotify_cache.py"""

import sqlite3

from sgs.constants import PLAYLIST_SOURCE_NAME
from sgs.spotify_cache import SpotifyCache


# Testing the "__init__" method from the "SpotifyCache" class.


def test_init_creates_all_tables(cache_path):
    """Opening the cache creates every table in the schema."""
    with SpotifyCache():
        pass

    connection = sqlite3.connect(cache_path)
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    connection.close()

    table_names = {row[0] for row in rows}
    assert table_names >= {
        "songs",
        "artists",
        "genres",
        "artist_genres",
        "song_artists",
        "playlists",
        "playlist_songs",
        "library_items",
        "album_songs",
        "top_track_rankings",
        "song_sources",
    }


# Testing the "get_songs_for_source" method from the "SpotifyCache" class.


def test_get_songs_for_source_returns_only_requested_source(cache_path):
    """Songs from other sources are not returned."""
    with SpotifyCache() as cache:
        cache._connection.execute(
            "INSERT INTO songs (song_id, name, uri) VALUES ('t1', 'Song', 'uri')"
        )
        cache._connection.execute(
            "INSERT INTO song_sources (song_id, source_name) VALUES ('t1', 'liked_songs')"
        )
        songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    assert songs == []
