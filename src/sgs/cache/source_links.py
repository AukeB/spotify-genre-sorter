"""Keeps the song_sources rows of each source in line with the cached data."""

import sqlite3

from sgs.cache.sync_stats import SyncStats


class SourceLinks:
    """Links songs to the sources they were found in.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Receives the count of rows added.
    """

    def __init__(self, connection: sqlite3.Connection, stats: SyncStats) -> None:
        """Creates the link writer on an open connection.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
            stats (SyncStats): Receives the count of rows added.
        """
        self._connection = connection
        self._stats = stats

    def rebuild(
        self, source_name: str, song_ids_sql: str, params: tuple[str, ...] = ()
    ) -> None:
        """Makes one source's rows in song_sources match the cached data.

        Only rows that no longer belong to the source are deleted, and only rows
        that are new are inserted, so unchanged rows are left alone.

        Args:
            source_name (str): The source whose rows are rebuilt.
            song_ids_sql (str): A SELECT statement that returns the song IDs
                belonging to the source in a column named song_id.
            params (tuple[str, ...]): Values for the placeholders in
                song_ids_sql.
        """
        with self._connection:
            self._connection.execute(
                "DELETE FROM song_sources WHERE source_name = ? "
                f"AND song_id NOT IN ({song_ids_sql})",
                (source_name, *params),
            )

            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO song_sources (song_id, source_name) "
                f"SELECT DISTINCT song_id, ? FROM ({song_ids_sql})",
                (source_name, *params),
            )

            self._stats.count_added("song_sources", cursor.rowcount)
