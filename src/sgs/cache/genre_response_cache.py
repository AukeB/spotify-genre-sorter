"""Stores the raw genre responses of MusicBrainz and Last.fm for each artist.

Each source gets its own row per artist in artist_genre_responses, holding the
JSON it returned. Nothing is parsed here. An artist is requested from a source
only if it has no row for that source yet, so a run that stops partway resumes
where it left off.
"""

import json
import logging
import sqlite3

from sgs.api.lastfm_api import fetch_lastfm_top_tags
from sgs.api.musicbrainz_api import fetch_musicbrainz_artist
from sgs.cache.sync_stats import SyncStats
from sgs.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

MUSICBRAINZ_SOURCE = "musicbrainz"
LASTFM_SOURCE = "lastfm"


class GenreResponseCache:
    """Requests genre data for artists that have no response from a source yet.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Receives the counts of rows added.
    """

    def __init__(self, connection: sqlite3.Connection, stats: SyncStats) -> None:
        """Creates the genre response cache.

        Args:
            connection (sqlite3.Connection): Open connection to the cache file.
            stats (SyncStats): Receives the counts of rows added.
        """

        self._connection = connection
        self._stats = stats

    def _pending_artists(self, source: str) -> list[tuple[str, str]]:
        """Returns the artists that have no response from a source yet.

        Args:
            source (str): MUSICBRAINZ_SOURCE or LASTFM_SOURCE.

        Returns:
            artists (list[tuple[str, str]]): The Spotify artist ID and name of
                each pending artist.
        """

        rows = self._connection.execute(
            "SELECT artist_id, name FROM artists "
            "WHERE artist_id NOT IN "
            "(SELECT artist_id FROM artist_genre_responses WHERE source = ?) "
            "ORDER BY artist_id",
            (source,),
        ).fetchall()

        artists = [(row[0], row[1]) for row in rows]

        return artists

    def _log_start(
        self, source_label: str, source: str, pending: list[tuple[str, str]]
    ) -> None:
        """Logs how many artists are already stored for a source, and how many
        are left.

        Args:
            source_label (str): The name shown in the log, such as
                "MusicBrainz".
            source (str): MUSICBRAINZ_SOURCE or LASTFM_SOURCE.
            pending (list[tuple[str, str]]): The artists that still need a
                request.
        """

        total_row = self._connection.execute("SELECT COUNT(*) FROM artists").fetchone()
        total = total_row[0]
        already_stored = total - len(pending)

        pending_count = len(pending)

        logger.info(
            "%s: %d artists already stored, skipping them. %d to request",
            source_label,
            already_stored,
            pending_count,
        )

    def _store(self, artist_id: str, source: str, result: dict) -> None:
        """Stores the raw response of one source for one artist.

        Args:
            artist_id (str): The Spotify artist ID.
            source (str): MUSICBRAINZ_SOURCE or LASTFM_SOURCE.
            result (dict): The status and raw payload returned by the source
                client.
        """

        payload = json.dumps(result["payload"])

        fetched_at = utc_now()

        with self._connection:
            self._connection.execute(
                "INSERT INTO artist_genre_responses (artist_id, source, fetched_at, status, payload) "
                "VALUES (?, ?, ?, ?, ?)",
                (artist_id, source, fetched_at, result["status"], payload),
            )

        self._stats.count_added("artist_genre_responses")

    def _sync_musicbrainz(self) -> None:
        """Requests MusicBrainz for every artist that has no MusicBrainz
        response yet.
        """

        pending = self._pending_artists(MUSICBRAINZ_SOURCE)
        matched = 0
        self._log_start("MusicBrainz", MUSICBRAINZ_SOURCE, pending)

        for index, (artist_id, name) in enumerate(pending, start=1):
            result = fetch_musicbrainz_artist(artist_id)
            self._store(artist_id, MUSICBRAINZ_SOURCE, result)

            if result["status"] == "found":
                matched += 1

            pending_count = len(pending)

            logger.info(
                "MusicBrainz %d/%d: %s -> %s",
                index,
                pending_count,
                name,
                result["status"],
            )

        pending_count = len(pending)

        logger.info(
            "MusicBrainz: %d artists requested, %d matched", pending_count, matched
        )

    def _sync_lastfm(self, api_key: str) -> None:
        """Requests Last.fm for every artist that has no Last.fm response yet.

        Args:
            api_key (str): A Last.fm API key.
        """

        pending = self._pending_artists(LASTFM_SOURCE)
        self._log_start("Last.fm", LASTFM_SOURCE, pending)

        for index, (artist_id, name) in enumerate(pending, start=1):
            result = fetch_lastfm_top_tags(name, api_key)
            self._store(artist_id, LASTFM_SOURCE, result)

            pending_count = len(pending)

            logger.info(
                "Last.fm %d/%d: %s -> %s", index, pending_count, name, result["status"]
            )

        pending_count = len(pending)
        logger.info("Last.fm: %d artists requested", pending_count)

    def sync(self, lastfm_api_key: str | None) -> None:
        """Requests both sources for the artists that are still missing a
        response.

        Last.fm is skipped when no API key is given.

        Args:
            lastfm_api_key (str | None): A Last.fm API key, or None to skip
                Last.fm.
        """

        self._sync_musicbrainz()

        if lastfm_api_key is None:
            logger.info("No Last.fm API key given, skipping Last.fm")

            return

        self._sync_lastfm(lastfm_api_key)
