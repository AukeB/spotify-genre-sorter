"""Keeps the cached playlists and their songs up to date."""

import logging
import sqlite3
from collections.abc import Iterable

from sgs.cache.source_links import SourceLinks
from sgs.cache.sync_stats import SyncStats
from sgs.utils.time_utils import utc_now
from sgs.cache.track_store import TrackStore
from sgs.constants import (
    PLAYLIST_SOURCE_NAME,
    SPOTIFY_API_BASE_URL,
    SPOTIFY_ME_PLAYLISTS_URL,
)
from sgs.api.spotify_api import get_all_pages, is_readable_playlist

logger = logging.getLogger(__name__)


def _filter_playable_tracks(entries: Iterable[dict]) -> list[dict]:
    """Returns the playable track objects from Spotify's playlist items.

    This runs during sync(), on items just fetched from the Spotify API. It does
    not read the database. Null items, local files, episodes, and tracks without
    an ID are skipped.

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


class PlaylistCache:
    """Caches the playlists the user can read and the songs in them.

    A playlist is read from Spotify only when its snapshot_id differs from the
    stored one. Playlists that are no longer readable are removed.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Receives the counts of rows added and changed.
        _track_store (TrackStore): Saves each song the playlists contain.
        _source_links (SourceLinks): Keeps the playlists source up to date.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        stats: SyncStats,
        track_store: TrackStore,
        source_links: SourceLinks,
    ) -> None:
        """Creates the playlist cache.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
            stats (SyncStats): Receives the counts of rows added and changed.
            track_store (TrackStore): Saves each song the playlists contain.
            source_links (SourceLinks): Keeps the playlists source up to date.
        """
        self._connection = connection
        self._stats = stats
        self._track_store = track_store
        self._source_links = source_links

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

    def _replace_playlist(self, playlist: dict, tracks: list[dict]) -> None:
        """Replaces a playlist and its songs in a single transaction.

        Args:
            playlist (dict): The playlist object from Spotify.
            tracks (list[dict]): The playable track objects, in playlist order.
        """
        synced_at = utc_now()

        if self._read_snapshot_id(playlist["id"]) is None:
            self._stats.count_added("playlists")
        else:
            self._stats.count_changed("playlists")

        self._stats.count_added("playlist_songs", len(tracks))

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
                self._track_store.store_track(track)

                self._connection.execute(
                    "INSERT INTO playlist_songs (playlist_id, position, song_id) "
                    "VALUES (?, ?, ?)",
                    (playlist["id"], position, track["id"]),
                )

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

    def _remove_unreadable(self, readable_ids: list[str]) -> None:
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

    def sync(
        self, access_token: str, user_id: str, include_collaborative: bool
    ) -> None:
        """Brings the cached playlists up to date with the Spotify account.

        Args:
            access_token (str): A valid Spotify access token.
            user_id (str): The ID of the logged-in user.
            include_collaborative (bool): Whether collaborative playlists owned
                by other users should be read.
        """
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
        self._remove_unreadable(readable_ids)
        self._source_links.rebuild(
            PLAYLIST_SOURCE_NAME,
            "SELECT song_id FROM playlist_songs",
        )
