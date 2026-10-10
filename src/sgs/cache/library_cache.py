"""Caches the liked songs and saved albums of the user.

Both lists are ordered by when each item was added, newest first. A sync reads
from the top and stops at the first item already cached. If the total on Spotify
no longer matches the cache, the whole list is read again so that removals are
noticed.
"""

import logging
import sqlite3
from collections.abc import Iterable

from sgs.cache.source_links import SourceLinks
from sgs.cache.sync_stats import SyncStats
from sgs.cache.track_filters import usable_tracks
from sgs.cache.track_store import TrackStore
from sgs.constants import (
    LIKED_SOURCE_NAME,
    SAVED_ALBUMS_SOURCE_NAME,
    SPOTIFY_API_BASE_URL,
    SPOTIFY_ME_ALBUMS_URL,
    SPOTIFY_ME_TRACKS_URL,
)

from sgs.api.spotify_api import fetch_total, get_all_pages

logger = logging.getLogger(__name__)


class LibraryCache:
    """Shared sync logic for a list of saved items.

    Subclasses set the list and the source they belong to, and say how an item
    is read and stored.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Receives the counts of rows added and changed.
        _track_store (TrackStore): Saves tracks.
        _source_links (SourceLinks): Keeps the source's song links up to date.
        _source_name (str): Source name stored in library_items.
        _list_url (str): Spotify endpoint that lists the saved items.
        _label (str): Human-readable name used in log messages.
        _song_ids_sql (str): Query for the song IDs in this source.
    """

    _source_name: str = ""
    _list_url: str = ""
    _label: str = ""
    _song_ids_sql: str = ""

    def __init__(
        self,
        connection: sqlite3.Connection,
        stats: SyncStats,
        track_store: TrackStore,
        source_links: SourceLinks,
    ) -> None:
        """Creates the library cache.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
            stats (SyncStats): Receives the counts of rows added and changed.
            track_store (TrackStore): Saves tracks.
            source_links (SourceLinks): Keeps the source's song links up to
                date.
        """
        self._connection = connection
        self._stats = stats
        self._track_store = track_store
        self._source_links = source_links

    def _is_known(self, item_id: str, added_at: str) -> bool:
        """Checks whether an item is already cached with the same added_at.

        Args:
            item_id (str): The track ID or album ID.
            added_at (str): When the item was added, from Spotify.

        Returns:
            known (bool): True if the item is cached as it is now.
        """
        row = self._connection.execute(
            "SELECT added_at FROM library_items WHERE source_name = ? AND item_id = ?",
            (self._source_name, item_id),
        ).fetchone()

        known = row is not None and row[0] == added_at

        return known

    def _upsert(self, item_id: str, added_at: str) -> None:
        """Stores or updates one library entry.

        Args:
            item_id (str): The track ID or album ID.
            added_at (str): When the item was added, from Spotify.
        """
        row = self._connection.execute(
            "SELECT added_at FROM library_items WHERE source_name = ? AND item_id = ?",
            (self._source_name, item_id),
        ).fetchone()

        # Only items whose added_at differs from the cache reach this method, so an
        # existing row always means a changed one.
        if row is None:
            self._stats.count_added("library_items")
        else:
            self._stats.count_changed("library_items")

        self._connection.execute(
            "INSERT INTO library_items (source_name, item_id, added_at) VALUES (?, ?, ?) "
            "ON CONFLICT(source_name, item_id) DO UPDATE SET added_at = excluded.added_at",
            (self._source_name, item_id, added_at),
        )

    def _count_cached(self) -> int:
        """Returns how many items of this source are cached.

        Returns:
            count (int): The number of cached items.
        """
        row = self._connection.execute(
            "SELECT COUNT(*) FROM library_items WHERE source_name = ?",
            (self._source_name,),
        ).fetchone()

        count = row[0]

        return count

    def _delete_not_in(self, kept_ids: set[str]) -> list[str]:
        """Deletes cached items that are no longer on the account.

        Args:
            kept_ids (set[str]): IDs of the items that are still on the account.

        Returns:
            removed_ids (list[str]): IDs of the items that were deleted.
        """
        rows = self._connection.execute(
            "SELECT item_id FROM library_items WHERE source_name = ?",
            (self._source_name,),
        ).fetchall()

        removed_ids = [row[0] for row in rows if row[0] not in kept_ids]

        for item_id in removed_ids:
            self._connection.execute(
                "DELETE FROM library_items WHERE source_name = ? AND item_id = ?",
                (self._source_name, item_id),
            )

        return removed_ids

    def _item_id(self, item: dict) -> str | None:
        """Returns the ID that identifies an item, or None if it is unusable.

        Args:
            item (dict): One item from the list endpoint.

        Returns:
            item_id (str | None): The track or album ID.
        """
        raise NotImplementedError

    def _store_item(self, item: dict, access_token: str) -> None:
        """Stores an item and everything it needs.

        Args:
            item (dict): One item from the list endpoint.
            access_token (str): A valid Spotify access token.
        """
        raise NotImplementedError

    def _on_removed(self, removed_ids: list[str]) -> None:
        """Cleans up anything stored for items that were removed.

        Args:
            removed_ids (list[str]): IDs of the removed items.
        """
        return None

    def _collect_new_items(self, pages: Iterable[dict]) -> list[dict]:
        """Collects the items added since the last sync, from the top of the
        list.

        Args:
            pages (Iterable[dict]): Items in list order, newest first.

        Returns:
            new_items (list[dict]): The items that are not cached yet.
        """
        new_items = []

        for item in pages:
            item_id = self._item_id(item)

            if item_id is None:
                continue

            if self._is_known(item_id, item["added_at"]):
                break

            new_items.append(item)

        return new_items

    def _resync(self, access_token: str) -> None:
        """Reads the whole list again, storing new items and removing old ones.

        Args:
            access_token (str): A valid Spotify access token.
        """
        pages = get_all_pages(
            self._list_url, access_token, description=self._label.lower()
        )

        kept_ids: set[str] = set()

        for item in pages:
            item_id = self._item_id(item)

            if item_id is None:
                continue

            kept_ids.add(item_id)

            if not self._is_known(item_id, item["added_at"]):
                self._store_item(item, access_token)

        with self._connection:
            removed_ids = self._delete_not_in(kept_ids)

        self._on_removed(removed_ids)

    def sync(self, access_token: str) -> None:
        """Brings the cached items up to date with the Spotify account.

        Args:
            access_token (str): A valid Spotify access token.
        """
        total = fetch_total(self._list_url, access_token)
        pages = get_all_pages(
            self._list_url, access_token, description=self._label.lower()
        )

        new_items = self._collect_new_items(pages)

        for item in new_items:
            self._store_item(item, access_token)

        cached_total = self._count_cached()

        if cached_total != total:
            logger.info(
                "%s differ (%d cached, %d on Spotify), reading all again",
                self._label,
                cached_total,
                total,
            )

            self._resync(access_token)

        self._source_links.rebuild(
            self._source_name,
            self._song_ids_sql,
            (self._source_name,),
        )


class LikedSongsCache(LibraryCache):
    """Caches the tracks in the user's library.

    Attributes:
        _source_name (str): LIKED_SOURCE_NAME.
        _list_url (str): The saved tracks endpoint.
        _label (str): "Liked songs".
        _song_ids_sql (str): Song IDs are the item IDs for liked songs.
    """

    _source_name = LIKED_SOURCE_NAME
    _list_url = SPOTIFY_ME_TRACKS_URL
    _label = "Liked songs"
    _song_ids_sql = "SELECT item_id AS song_id FROM library_items WHERE source_name = ?"

    def _item_id(self, item: dict) -> str | None:
        """Returns the track ID of a saved track, or None for a null track.

        Args:
            item (dict): One saved-track item from Spotify.

        Returns:
            item_id (str | None): The track ID.
        """
        track = item.get("track")

        if track is None:
            return None

        item_id = track["id"]

        return item_id

    def _store_item(self, item: dict, access_token: str) -> None:
        """Stores a liked track and its library entry.

        Args:
            item (dict): One saved-track item from Spotify.
            access_token (str): Unused. Kept so every library cache has the same
                signature.
        """
        track = item["track"]

        with self._connection:
            self._track_store.store_track(track)
            self._upsert(track["id"], item["added_at"])


class SavedAlbumsCache(LibraryCache):
    """Caches the albums in the user's library and their tracks.

    An album's tracks are fetched once, when the album is first seen, and kept
    until the album is removed.

    Attributes:
        _source_name (str): SAVED_ALBUMS_SOURCE_NAME.
        _list_url (str): The saved albums endpoint.
        _label (str): "Saved albums".
        _song_ids_sql (str): Song IDs come from the album_songs table.
    """

    _source_name = SAVED_ALBUMS_SOURCE_NAME
    _list_url = SPOTIFY_ME_ALBUMS_URL
    _label = "Saved albums"
    _song_ids_sql = (
        "SELECT album_songs.song_id FROM album_songs "
        "JOIN library_items ON library_items.item_id = album_songs.album_id "
        "WHERE library_items.source_name = ?"
    )

    def _item_id(self, item: dict) -> str | None:
        """Returns the album ID of a saved album.

        Args:
            item (dict): One saved-album item from Spotify.

        Returns:
            item_id (str | None): The album ID.
        """
        album = item["album"]
        item_id = album["id"]

        return item_id

    def _store_item(self, item: dict, access_token: str) -> None:
        """Fetches an album's tracks and stores them with the album.

        Args:
            item (dict): One saved-album item from Spotify.
            access_token (str): A valid Spotify access token.
        """
        album = item["album"]
        self._track_store.store_album(album)
        tracks_url = f"{SPOTIFY_API_BASE_URL}/albums/{album['id']}/tracks"
        description = f'album "{album["name"]}"'
        pages = get_all_pages(tracks_url, access_token, description=description)
        tracks = usable_tracks(pages)

        with self._connection:
            self._connection.execute(
                "DELETE FROM album_songs WHERE album_id = ?",
                (album["id"],),
            )

            for position, track in enumerate(tracks):
                self._track_store.store_track(track)

                self._connection.execute(
                    "INSERT INTO album_songs (album_id, position, song_id) "
                    "VALUES (?, ?, ?)",
                    (album["id"], position, track["id"]),
                )

            self._upsert(album["id"], item["added_at"])

    def _on_removed(self, removed_ids: list[str]) -> None:
        """Deletes the tracks of albums that were removed from the library.

        Args:
            removed_ids (list[str]): IDs of the removed albums.
        """
        with self._connection:
            for album_id in removed_ids:
                self._connection.execute(
                    "DELETE FROM album_songs WHERE album_id = ?",
                    (album_id,),
                )
