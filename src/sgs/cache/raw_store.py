"""Keeps the Spotify track, album, and artist objects exactly as they were
returned.

The parsed tables are what the app queries. These raw copies are a backup, so
that fields Spotify removes later can still be read, and so the data can be
parsed again without calling Spotify.
"""

import json
import sqlite3

from sgs.utils.time_utils import utc_now

RAW_TRACKS_TABLE = "raw_tracks"
RAW_ALBUMS_TABLE = "raw_albums"
RAW_ARTISTS_TABLE = "raw_artists"


class RawStore:
    """Writes the raw JSON of each Spotify object, one row per object.

    A later copy of the same object replaces the earlier one, and fetched_at
    records when that copy was taken.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Creates the raw store on an open connection.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
        """

        self._connection = connection

    def _upsert(self, table: str, id_column: str, object_id: str, data: dict) -> None:
        """Stores one object as JSON, replacing an earlier copy of the same
        object.

        Args:
            table (str): One of the raw table names defined in this module.
            id_column (str): The primary key column of that table.
            object_id (str): The Spotify ID of the object.
            data (dict): The object as Spotify returned it.
        """

        payload = json.dumps(data)
        fetched_at = utc_now()

        self._connection.execute(
            f"INSERT INTO {table} ({id_column}, fetched_at, payload) VALUES (?, ?, ?) "
            f"ON CONFLICT({id_column}) DO UPDATE SET "
            "fetched_at = excluded.fetched_at, payload = excluded.payload",
            (object_id, fetched_at, payload),
        )

    def store_track(self, track: dict) -> None:
        """Stores a raw track object.

        Args:
            track (dict): A track object from Spotify.
        """

        self._upsert(RAW_TRACKS_TABLE, "song_id", track["id"], track)

    def store_album(self, album: dict) -> None:
        """Stores a raw album object.

        Args:
            album (dict): An album object from Spotify.
        """

        self._upsert(RAW_ALBUMS_TABLE, "album_id", album["id"], album)

    def store_artist(self, artist: dict) -> None:
        """Stores a raw artist object, as it appears inside a track.

        Args:
            artist (dict): A simplified artist object from Spotify.
        """

        self._upsert(RAW_ARTISTS_TABLE, "artist_id", artist["id"], artist)
