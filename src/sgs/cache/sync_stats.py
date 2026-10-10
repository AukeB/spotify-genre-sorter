"""Counts and timing for one sync, logged at the end of it."""

import logging
import time
from collections import Counter

logger = logging.getLogger(__name__)


class SyncStats:
    """Collects how many rows a sync added and changed, and how long it took.

    Attributes:
        _added (Counter[str]): Rows added during the current sync, per table.
        _changed (Counter[str]): Existing rows whose values changed, per table.

    Example:
        >>> stats = SyncStats()
        >>> start = stats.start_sync()
        >>> stats.count_added("songs")
        >>> stats.finish_sync("Playlist", start)
    """

    def __init__(self) -> None:
        """Creates empty counters."""
        self._added: Counter[str] = Counter()
        self._changed: Counter[str] = Counter()

    def count_added(self, table: str, amount: int = 1) -> None:
        """Adds to the number of rows added to a table.

        Args:
            table (str): The table name.
            amount (int): How many rows were added. Defaults to 1.
        """
        self._added[table] += amount

    def count_changed(self, table: str) -> None:
        """Counts one existing row whose values changed.

        Args:
            table (str): The table name.
        """
        self._changed[table] += 1

    def start_sync(self) -> float:
        """Clears the counters and starts the timer for a sync.

        Returns:
            start (float): The start time from time.perf_counter().
        """
        self._added.clear()
        self._changed.clear()
        start = time.perf_counter()

        return start

    def _log_changes(self) -> None:
        """Logs how many rows were added and changed during the last sync."""
        logger.info("Cache rows added: %s", dict(self._added))
        logger.info("Cache rows changed: %s", dict(self._changed))

    def finish_sync(self, name: str, start: float) -> None:
        """Logs the counts and how long the sync took.

        Args:
            name (str): The name of the sync, used in the log message.
            start (float): The start time returned by start_sync().
        """
        self._log_changes()

        elapsed = time.perf_counter() - start
        logger.info("%s sync took %.2f s", name, elapsed)
