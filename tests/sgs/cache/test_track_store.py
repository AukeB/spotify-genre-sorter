"""Module for testing track_store.py"""

import json
import sqlite3

from sgs.cache.raw_store import RAW_ALBUMS_TABLE, RAW_ARTISTS_TABLE, RAW_TRACKS_TABLE
from sgs.cache.schema import create_schema
from sgs.cache.sync_stats import SyncStats
from sgs.cache.track_store import TrackStore


def _track(track_id):
    """Builds a track object with one artist and an album, as Spotify returns them."""
    track = {
        "id": track_id,
        "name": f"Song {track_id}",
        "uri": f"spotify:track:{track_id}",
        "artists": [{"id": "ar1", "name": "Artist"}],
        "album": {"id": "al1", "name": "Album"},
    }

    return track


# Testing the "store_track" method from the "TrackStore" class.


def test_store_track_keeps_raw_track_album_and_artist():
    """A track also stores its raw track, album, and artist objects."""
    connection = sqlite3.connect(":memory:")
    create_schema(connection)
    stats = SyncStats()

    TrackStore(connection, stats).store_track(_track("t1"))

    track_payload = connection.execute(f"SELECT payload FROM {RAW_TRACKS_TABLE}").fetchone()[0]
    album_id = connection.execute(f"SELECT album_id FROM {RAW_ALBUMS_TABLE}").fetchone()[0]
    artist_id = connection.execute(f"SELECT artist_id FROM {RAW_ARTISTS_TABLE}").fetchone()[0]

    assert json.loads(track_payload)["album"]["name"] == "Album"
    assert album_id == "al1"
    assert artist_id == "ar1"


# Testing the "store_album" method from the "TrackStore" class.


def test_store_album_keeps_raw_album():
    """An album object from the saved-albums list is kept as raw JSON."""
    connection = sqlite3.connect(":memory:")
    create_schema(connection)
    stats = SyncStats()

    TrackStore(connection, stats).store_album({"id": "al2", "name": "Saved"})
    row = connection.execute(f"SELECT album_id FROM {RAW_ALBUMS_TABLE}").fetchone()

    assert row[0] == "al2"
