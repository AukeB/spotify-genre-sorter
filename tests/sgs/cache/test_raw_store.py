"""Module for testing raw_store.py"""

import json
import sqlite3

from sgs.cache.raw_store import RAW_ALBUMS_TABLE, RAW_ARTISTS_TABLE, RAW_TRACKS_TABLE, RawStore
from sgs.cache.schema import create_schema


def _connection():
    """Opens an in-memory cache with every table created."""
    connection = sqlite3.connect(":memory:")
    create_schema(connection)

    return connection


# Testing the "store_track" method from the "RawStore" class.


def test_store_track_keeps_the_object_as_json():
    """The track is stored as the JSON Spotify returned, keyed by its ID."""
    connection = _connection()
    track = {"id": "t1", "name": "Song", "extra_field": [1, 2]}

    RawStore(connection).store_track(track)
    row = connection.execute(f"SELECT song_id, payload FROM {RAW_TRACKS_TABLE}").fetchone()

    assert row[0] == "t1"
    assert json.loads(row[1]) == track


def test_store_track_replaces_an_earlier_copy():
    """Storing the same track again keeps one row with the latest JSON."""
    connection = _connection()
    raw = RawStore(connection)

    raw.store_track({"id": "t1", "name": "Old"})
    raw.store_track({"id": "t1", "name": "New"})
    rows = connection.execute(f"SELECT payload FROM {RAW_TRACKS_TABLE}").fetchall()

    assert len(rows) == 1
    assert json.loads(rows[0][0])["name"] == "New"


# Testing the "store_album" method from the "RawStore" class.


def test_store_album_keys_by_album_id():
    """Albums are stored in their own table, keyed by album ID."""
    connection = _connection()

    RawStore(connection).store_album({"id": "a1", "name": "Album"})
    row = connection.execute(f"SELECT album_id FROM {RAW_ALBUMS_TABLE}").fetchone()

    assert row[0] == "a1"


# Testing the "store_artist" method from the "RawStore" class.


def test_store_artist_keys_by_artist_id():
    """Artists are stored in their own table, keyed by artist ID."""
    connection = _connection()

    RawStore(connection).store_artist({"id": "ar1", "name": "Artist"})
    row = connection.execute(f"SELECT artist_id FROM {RAW_ARTISTS_TABLE}").fetchone()

    assert row[0] == "ar1"
