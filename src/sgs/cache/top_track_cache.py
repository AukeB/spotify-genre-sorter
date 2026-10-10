"""Caches the user's top tracks for each time range."""

import logging
import sqlite3

from sgs.cache.source_links import SourceLinks
from sgs.cache.sync_stats import SyncStats
from sgs.cache.time_utils import utc_cutoff, utc_now
from sgs.cache.track_filters import usable_tracks
from sgs.cache.track_store import TrackStore
from sgs.constants import (
    SPOTIFY_ME_TOP_TRACKS_URL,
    TOP_TRACKS_MAX_AGE_HOURS,
    TOP_TRACKS_SOURCE_NAME,
)
from sgs.spotify_api import get_all_pages

logger = logging.getLogger(__name__)


class TopTrackCache:
    """Caches the ranking of top tracks for each time range.

    A ranking has no change marker, so it is read again only when the cached one
    is older than TOP_TRACKS_MAX_AGE_HOURS.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Receives the counts of rows added.
        _track_store (TrackStore): Saves each ranked track.
        _source_links (SourceLinks): Keeps the top tracks source up to date.
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        stats: SyncStats,
        track_store: TrackStore,
        source_links: SourceLinks,
    ) -> None:
        """Creates the top track cache.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
            stats (SyncStats): Receives the counts of rows added.
            track_store (TrackStore): Saves each ranked track.
            source_links (SourceLinks): Keeps the top tracks source up to date.
        """
        self._connection = connection
        self._stats = stats
        self._track_store = track_store
        self._source_links = source_links

    def _has_fresh_ranking(self, time_range: str) -> bool:
        """Checks whether the cached ranking for a time range is recent enough.

        Args:
            time_range (str): The Spotify time range, such as "medium_term".

        Returns:
            fresh (bool): True if the ranking is newer than
                TOP_TRACKS_MAX_AGE_HOURS.
        """
        row = self._connection.execute(
            "SELECT MAX(fetched_at) FROM top_track_rankings WHERE time_range = ?",
            (time_range,),
        ).fetchone()
        last_fetched = row[0]

        if last_fetched is None:
            return False

        cutoff = utc_cutoff(TOP_TRACKS_MAX_AGE_HOURS)
        fresh = last_fetched >= cutoff

        return fresh

    def _replace_ranking(self, time_range: str, access_token: str) -> None:
        """Reads the top tracks for a time range and replaces the cached
        ranking.

        Args:
            time_range (str): The Spotify time range, such as "medium_term".
            access_token (str): A valid Spotify access token.
        """
        pages = get_all_pages(
            SPOTIFY_ME_TOP_TRACKS_URL,
            access_token,
            params={"time_range": time_range},
            description=f"top tracks ({time_range})",
        )
        tracks = usable_tracks(pages)
        fetched_at = utc_now()

        with self._connection:
            self._connection.execute(
                "DELETE FROM top_track_rankings WHERE time_range = ?",
                (time_range,),
            )

            for position, track in enumerate(tracks):
                self._track_store.store_track(track)

                self._connection.execute(
                    "INSERT INTO top_track_rankings (time_range, position, song_id, fetched_at) "
                    "VALUES (?, ?, ?, ?)",
                    (time_range, position, track["id"], fetched_at),
                )

        self._stats.count_added("top_track_rankings", len(tracks))

    def sync(self, access_token: str, time_range: str) -> None:
        """Brings the cached top tracks for a time range up to date.

        Args:
            access_token (str): A valid Spotify access token.
            time_range (str): The Spotify time range, such as "medium_term".
        """
        if self._has_fresh_ranking(time_range):
            logger.info("Top tracks (%s) are up to date, skipping", time_range)
        else:
            self._replace_ranking(time_range, access_token)

        self._source_links.rebuild(
            TOP_TRACKS_SOURCE_NAME,
            "SELECT song_id FROM top_track_rankings WHERE time_range = ?",
            (time_range,),
        )
