"""Local SQLite cache of the Spotify data the genre sorter needs.

The cache keeps only the songs, artists, and playlists the app uses. A playlist
whose snapshot_id has not changed is not read from Spotify again. The table
layout is described in docs/spotify_cache.md.
"""

import logging
import sqlite3
import time
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from sgs.constants import CACHE_DB_PATH, SPOTIFY_API_BASE_URL, SPOTIFY_ME_PLAYLISTS_URL
from sgs.models import Song
from sgs.spotify_api import get_all_pages, is_readable_playlist

logger = logging.getLogger(__name__)

PLAYLIST_SOURCE_NAME = "your_playlists"

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    song_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uri TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artists (
    artist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    genres_fetched_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genres (
    genre_name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS artist_genres (
    artist_id TEXT REFERENCES artists(artist_id),
    genre_name TEXT REFERENCES genres(genre_name),
    PRIMARY KEY (artist_id, genre_name)
);

CREATE TABLE IF NOT EXISTS song_artists (
    song_id TEXT REFERENCES songs(song_id),
    artist_id TEXT REFERENCES artists(artist_id),
    position INTEGER NOT NULL,
    PRIMARY KEY (song_id, artist_id)
);

CREATE TABLE IF NOT EXISTS playlists (
    playlist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    collaborative BOOLEAN NOT NULL,
    snapshot_id TEXT NOT NULL,
    synced_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id TEXT REFERENCES playlists(playlist_id),
    position INTEGER NOT NULL,
    song_id TEXT REFERENCES songs(song_id),
    PRIMARY KEY (playlist_id, position)
);

CREATE TABLE IF NOT EXISTS song_sources (
    song_id TEXT REFERENCES songs(song_id),
    source_name TEXT NOT NULL,
    PRIMARY KEY (song_id, source_name)
);
"""


def _filter_playable_tracks(entries: Iterable[dict]) -> list[dict]:
    """Returns the playable track objects from Spotify's playlist items.

    This runs during sync_playlists(), on items just fetched from the Spotify
    API. It does not read the database. Null items, local files, episodes, and
    tracks without an ID are skipped.

    Args:
        entries (Iterable[dict]): Playlist item objects returned by the Spotify
            playlist items endpoint.

    Returns:
        tracks (list[dict]): The track objects, in playlist order.
    """
    tracks = []

    for entry in entries:
        item = entry.get("item")

        if item is None or entry.get("is_local") or item.get("type") != "track":
            continue

        if item.get("id") is None:
            continue

        tracks.append(item)

    return tracks


def _utc_now() -> str:
    """Returns the current UTC time as an ISO 8601 string.

    Returns:
        timestamp (str): The current time, for example
            2026-10-10T12:00:00+00:00.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()

    return timestamp


class SpotifyCache:
    """Local cache of songs, artists, and playlists read from Spotify.

    The cache is a subset of the Spotify data, kept in SQLite so that repeated
    runs do not call the API again for data that has not changed.

    The usual flow has two steps:

    1. sync_playlists() asks Spotify for the account's playlists and keeps only
       the readable ones. For each playlist, it compares snapshot_id with the
       stored value. If they match, the playlist is skipped. If not, its items
       are read and its rows are replaced in one transaction. Playlists that are
       no longer readable are deleted, and the songs from the playlists source
       are recomputed.
    2. get_songs_for_source() reads the cached songs for one source from the
       database. It makes no API calls, so it can run as often as needed.

    Sync must run before reading, otherwise the cache may be empty or stale.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _added (Counter[str]): Rows added during the current sync, per table.
        _changed (Counter[str]): Existing rows whose values changed during the
            current sync, per table.

    Example:
        >>> with SpotifyCache() as cache:
        ...     cache.sync_playlists(access_token, user_id, include_collaborative=True)
        ...     songs = cache.get_songs_for_source("your_playlists")
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Opens the cache file and creates any tables that are missing.

        Args:
            db_path (Path | None): Location of the cache file. Defaults to
                CACHE_DB_PATH when not given.
        """
        path = db_path or CACHE_DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(SCHEMA)

        self._added: Counter[str] = Counter()
        self._changed: Counter[str] = Counter()

    def _read_snapshot_id(self, playlist_id: str) -> str | None:
        """Returns the snapshot_id stored for a playlist.

        Args:
            playlist_id (str): The Spotify playlist ID.

        Returns:
            snapshot_id (str | None): The stored snapshot, or None if the
                playlist has not been cached yet.
        """
        row = self._connection.execute(
            "SELECT snapshot_id FROM playlists WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()
        snapshot_id = row[0] if row else None

        return snapshot_id

    def _store_track(self, track: dict) -> None:
        """Saves a track, its artists, and the links between them.

        Args:
            track (dict): A track object from Spotify.
        """
        song_row = self._connection.execute(
            "SELECT name, uri FROM songs WHERE song_id = ?",
            (track["id"],),
        ).fetchone()

        if song_row is None:
            self._added["songs"] += 1
        elif song_row != (track["name"], track["uri"]):
            self._changed["songs"] += 1

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
            artist_row = self._connection.execute(
                "SELECT name FROM artists WHERE artist_id = ?",
                (artist["id"],),
            ).fetchone()

            if artist_row is None:
                self._added["artists"] += 1
            elif artist_row[0] != artist["name"]:
                self._changed["artists"] += 1

            self._connection.execute(
                "INSERT INTO artists (artist_id, name) VALUES (?, ?) "
                "ON CONFLICT(artist_id) DO UPDATE SET name = excluded.name",
                (artist["id"], artist["name"]),
            )

            self._connection.execute(
                "INSERT INTO song_artists (song_id, artist_id, position) "
                "VALUES (?, ?, ?)",
                (track["id"], artist["id"], position),
            )

    def _replace_playlist(self, playlist: dict, tracks: list[dict]) -> None:
        """Replaces a playlist and its songs in a single transaction.

        Args:
            playlist (dict): The playlist object from Spotify.
            tracks (list[dict]): The playable track objects, in playlist order.
        """
        synced_at = _utc_now()

        if self._read_snapshot_id(playlist["id"]) is None:
            self._added["playlists"] += 1
        else:
            self._changed["playlists"] += 1

        self._added["playlist_songs"] += len(tracks)

        with self._connection:
            self._connection.execute(
                "INSERT INTO playlists "
                "(playlist_id, name, owner_id, collaborative, snapshot_id, synced_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(playlist_id) DO UPDATE SET "
                "name = excluded.name, owner_id = excluded.owner_id, "
                "collaborative = excluded.collaborative, "
                "snapshot_id = excluded.snapshot_id, synced_at = excluded.synced_at",
                (
                    playlist["id"],
                    playlist["name"],
                    playlist["owner"]["id"],
                    playlist["collaborative"],
                    playlist["snapshot_id"],
                    synced_at,
                ),
            )

            self._connection.execute(
                "DELETE FROM playlist_songs WHERE playlist_id = ?",
                (playlist["id"],),
            )

            for position, track in enumerate(tracks):
                self._store_track(track)

                self._connection.execute(
                    "INSERT INTO playlist_songs (playlist_id, position, song_id) "
                    "VALUES (?, ?, ?)",
                    (playlist["id"], position, track["id"]),
                )

    def _count_cached_songs(self, playlist_id: str) -> int:
        """Returns how many songs are cached for a playlist.

        Args:
            playlist_id (str): The Spotify playlist ID.

        Returns:
            count (int): The number of songs stored for the playlist.
        """
        row = self._connection.execute(
            "SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()
        count = row[0]

        return count

    def _sync_playlist(self, playlist: dict, access_token: str) -> None:
        """Reads a playlist's songs from Spotify unless the cache is up to date.

        Args:
            playlist (dict): The playlist object from Spotify.
            access_token (str): A valid Spotify access token.
        """
        stored_snapshot_id = self._read_snapshot_id(playlist["id"])

        if stored_snapshot_id == playlist["snapshot_id"]:
            cached_count = self._count_cached_songs(playlist["id"])
            logger.info(
                "Playlist unchanged, skipping: %s (%d cached songs)",
                playlist["name"],
                cached_count,
            )
            return

        items_url = f"{SPOTIFY_API_BASE_URL}/playlists/{playlist['id']}/items"
        description = f'playlist "{playlist["name"]}"'
        pages = get_all_pages(items_url, access_token, description=description)
        entries = list(pages)
        tracks = _filter_playable_tracks(entries)
        self._replace_playlist(playlist, tracks)

        logger.info("Synced playlist %s: %d songs", playlist["name"], len(tracks))

    def _remove_unreadable_playlists(self, readable_ids: list[str]) -> None:
        """Deletes cached playlists that are no longer readable or were removed.

        Args:
            readable_ids (list[str]): IDs of the playlists that should stay
                cached.
        """
        marks = ["?"] * len(readable_ids)
        placeholders = ", ".join(marks)

        with self._connection:
            self._connection.execute(
                f"DELETE FROM playlist_songs WHERE playlist_id NOT IN ({placeholders})",
                readable_ids,
            )

            self._connection.execute(
                f"DELETE FROM playlists WHERE playlist_id NOT IN ({placeholders})",
                readable_ids,
            )

    def _rebuild_song_sources(self) -> None:
        """Makes the playlists source match the cached playlist songs.

        Only rows that no longer belong to a playlist are deleted, and only rows
        that are new are inserted, so unchanged rows are left alone.
        """
        with self._connection:
            self._connection.execute(
                "DELETE FROM song_sources WHERE source_name = ? "
                "AND song_id NOT IN (SELECT song_id FROM playlist_songs)",
                (PLAYLIST_SOURCE_NAME,),
            )

            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO song_sources (song_id, source_name) "
                "SELECT DISTINCT song_id, ? FROM playlist_songs",
                (PLAYLIST_SOURCE_NAME,),
            )
            self._added["song_sources"] += cursor.rowcount

    def _log_changes(self) -> None:
        """Logs how many rows were added and changed during the last sync."""
        logger.info("Cache rows added: %s", dict(self._added))
        logger.info("Cache rows changed: %s", dict(self._changed))

    def sync_playlists(
        self,
        access_token: str,
        user_id: str,
        include_collaborative: bool,
    ) -> None:
        """Brings the cached playlists up to date with the Spotify account.

        Playlists whose snapshot_id is unchanged are not read again. Playlists
        that are no longer readable, or were deleted, are removed from the
        cache.

        Args:
            access_token (str): A valid Spotify access token.
            user_id (str): The ID of the logged-in user.
            include_collaborative (bool): Whether collaborative playlists owned
                by other users should be read.
        """
        start = time.perf_counter()
        self._added.clear()
        self._changed.clear()
        pages = get_all_pages(SPOTIFY_ME_PLAYLISTS_URL, access_token)
        all_playlists = list(pages)

        readable = []

        for playlist in all_playlists:
            if is_readable_playlist(playlist, user_id, include_collaborative):
                readable.append(playlist)

        logger.info(
            "Found %d playlists, %d readable",
            len(all_playlists),
            len(readable),
        )

        for playlist in readable:
            self._sync_playlist(playlist, access_token)

        readable_ids = [playlist["id"] for playlist in readable]
        self._remove_unreadable_playlists(readable_ids)
        self._rebuild_song_sources()

        self._log_changes()

        elapsed = time.perf_counter() - start
        logger.info("Playlist sync took %.2f s", elapsed)

    def get_songs_for_source(self, source_name: str) -> list[Song]:
        """Reads the cached songs that were found in a source.

        Args:
            source_name (str): The source to read, such as "your_playlists".

        Returns:
            songs (list[Song]): The songs from that source, with their artist
                IDs in credit order.
        """
        song_rows = self._connection.execute(
            "SELECT songs.song_id, songs.name, songs.uri FROM songs "
            "JOIN song_sources ON song_sources.song_id = songs.song_id "
            "WHERE song_sources.source_name = ?",
            (source_name,),
        ).fetchall()

        artist_rows = self._connection.execute(
            "SELECT song_id, artist_id FROM song_artists ORDER BY song_id, position"
        ).fetchall()

        artist_ids_by_song: dict[str, list[str]] = {}

        for song_id, artist_id in artist_rows:
            artist_ids = artist_ids_by_song.setdefault(song_id, [])
            artist_ids.append(artist_id)

        songs = []

        for song_id, name, uri in song_rows:
            artist_ids = artist_ids_by_song.get(song_id, [])
            song = Song(
                id=song_id,
                name=name,
                uri=uri,
                artist_ids=artist_ids,
                sources={source_name},
            )
            songs.append(song)

        return songs

    def close(self) -> None:
        """Closes the connection to the cache file."""
        self._connection.close()

    def __enter__(self) -> "SpotifyCache":
        """Returns the cache so it can be used in a with block.

        Returns:
            cache (SpotifyCache): This cache instance.
        """
        cache = self

        return cache

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Closes the connection when the with block ends."""
        self.close()
