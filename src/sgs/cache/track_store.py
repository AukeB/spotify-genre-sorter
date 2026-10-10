"""Saves tracks, their artists, albums, and the links between them."""

import sqlite3

from sgs.cache.raw_store import RawStore
from sgs.cache.sync_stats import SyncStats


class TrackStore:
    """Writes track objects from Spotify into the songs and artists tables.

    Every source uses this, so a song is stored the same way wherever it was
    found.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Receives the counts of rows added and changed.
        _raw (RawStore): Keeps the raw JSON of every object.
    """

    def __init__(self, connection: sqlite3.Connection, stats: SyncStats) -> None:
        """Creates a track store on an open connection.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
            stats (SyncStats): Receives the counts of rows added and changed.
        """
        self._connection = connection
        self._stats = stats
        self._raw = RawStore(connection)

    def _store_artist(self, song_id: str, artist: dict, position: int) -> None:
        """Saves one artist and links it to a song.

        Args:
            song_id (str): The Spotify track ID of the song.
            artist (dict): A simplified artist object from Spotify.
            position (int): The artist's place in the credits, 0 is the first.
        """
        self._raw.store_artist(artist)

        artist_row = self._connection.execute(
            "SELECT name FROM artists WHERE artist_id = ?",
            (artist["id"],),
        ).fetchone()

        if artist_row is None:
            self._stats.count_added("artists")
        elif artist_row[0] != artist["name"]:
            self._stats.count_changed("artists")

        self._connection.execute(
            "INSERT INTO artists (artist_id, name) VALUES (?, ?) "
            "ON CONFLICT(artist_id) DO UPDATE SET name = excluded.name",
            (artist["id"], artist["name"]),
        )

        self._connection.execute(
            "INSERT INTO song_artists (song_id, artist_id, position) VALUES (?, ?, ?)",
            (song_id, artist["id"], position),
        )

    def store_track(self, track: dict) -> None:
        """Saves a track, its artists, and the links between them.

        Args:
            track (dict): A track object from Spotify.
        """
        self._raw.store_track(track)

        album = track.get("album")

        if album is not None:
            self._raw.store_album(album)

        song_row = self._connection.execute(
            "SELECT name, uri FROM songs WHERE song_id = ?",
            (track["id"],),
        ).fetchone()

        if song_row is None:
            self._stats.count_added("songs")
        elif song_row != (track["name"], track["uri"]):
            self._stats.count_changed("songs")

        self._connection.execute(
            "INSERT INTO songs (song_id, name, uri) VALUES (?, ?, ?) "
            "ON CONFLICT(song_id) DO UPDATE SET name = excluded.name, uri = excluded.uri",
            (track["id"], track["name"], track["uri"]),
        )

        self._connection.execute(
            "DELETE FROM song_artists WHERE song_id = ?",
            (track["id"],),
        )

        for position, artist in enumerate(track["artists"]):
            self._store_artist(track["id"], artist, position)

    def store_album(self, album: dict) -> None:
        """Keeps the raw copy of an album.

        Args:
            album (dict): An album object from Spotify.
        """
        self._raw.store_album(album)
