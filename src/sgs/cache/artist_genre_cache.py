"""Caches the genres of each artist.

Genres belong to artists, not to songs. Each artist's genres are stored
separately in artist_genres, so a song's genres are found by joining through
song_artists. An artist is requested from Spotify only once, when its
genres_fetched_at is still empty.
"""

import logging
import sqlite3
from collections.abc import Iterator

from sgs.cache.sync_stats import SyncStats
from sgs.cache.time_utils import utc_now
from sgs.constants import ARTISTS_PER_REQUEST
from sgs.spotify_api import get_artists

logger = logging.getLogger(__name__)


def _batches(artist_ids: list[str], size: int) -> Iterator[list[str]]:
    """Splits a list of IDs into batches no larger than size.

    Args:
        artist_ids (list[str]): The IDs to split.
        size (int): The largest batch to return.

    Yields:
        list[str]: One batch of IDs, in the original order.
    """
    for start in range(0, len(artist_ids), size):
        batch = artist_ids[start : start + size]

        yield batch


class ArtistGenreCache:
    """Stores the genres of each artist that has not been fetched yet.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Receives the counts of rows added.
    """

    def __init__(self, connection: sqlite3.Connection, stats: SyncStats) -> None:
        """Creates the artist genre cache.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
            stats (SyncStats): Receives the counts of rows added.
        """
        self._connection = connection
        self._stats = stats

    def _pending_artist_ids(self) -> list[str]:
        """Returns the IDs of artists whose genres have never been fetched.

        Returns:
            artist_ids (list[str]): The pending artist IDs, in ID order.
        """
        rows = self._connection.execute(
            "SELECT artist_id FROM artists WHERE genres_fetched_at IS NULL ORDER BY artist_id",
        ).fetchall()
        artist_ids = [row[0] for row in rows]

        return artist_ids

    def _store_artist(self, artist: dict, fetched_at: str) -> None:
        """Stores one artist's genres, replacing any earlier list for that
        artist.

        Args:
            artist (dict): The artist object from Spotify, with its genres.
            fetched_at (str): The time the genres were read, as ISO 8601.
        """
        genres = artist["genres"]

        for genre_name in genres:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO genres (genre_name) VALUES (?)",
                (genre_name,),
            )
            self._stats.count_added("genres", cursor.rowcount)

        self._connection.execute(
            "DELETE FROM artist_genres WHERE artist_id = ?",
            (artist["id"],),
        )

        for genre_name in genres:
            self._connection.execute(
                "INSERT INTO artist_genres (artist_id, genre_name) VALUES (?, ?)",
                (artist["id"], genre_name),
            )

        self._stats.count_added("artist_genres", len(genres))

        self._connection.execute(
            "UPDATE artists SET genres_fetched_at = ? WHERE artist_id = ?",
            (fetched_at, artist["id"]),
        )

    def _store_batch(self, artist_ids: list[str], access_token: str) -> int:
        """Fetches one batch of artists and stores the ones Spotify knows.

        Args:
            artist_ids (list[str]): IDs in this batch.
            access_token (str): A valid Spotify access token.

        Returns:
            missing (int): How many IDs Spotify did not return an artist for.
        """
        artists = get_artists(artist_ids, access_token)
        fetched_at = utc_now()
        missing = 0

        with self._connection:
            for artist in artists:
                if artist is None:
                    missing += 1
                    continue

                self._store_artist(artist, fetched_at)

        return missing

    def sync(self, access_token: str) -> None:
        """Fetches genres for every artist that does not have them yet.

        Args:
            access_token (str): A valid Spotify access token.
        """
        pending = self._pending_artist_ids()
        missing = 0

        for batch in _batches(pending, ARTISTS_PER_REQUEST):
            missing += self._store_batch(batch, access_token)

        if missing:
            logger.info(
                "%d artists were not found on Spotify, will try again next run", missing
            )
