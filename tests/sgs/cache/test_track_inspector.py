"""Module for testing track_inspector.py"""

import sqlite3
from pathlib import Path

import pytest

from sgs.cache.schema import create_schema
from sgs.cache.sync_stats import SyncStats
from sgs.cache.track_inspector import (
    build_track_report,
    open_read_only,
    parse_track_id,
)

from sgs.cache.track_store import TrackStore


def _track(track_id, uri=None):
    """Builds a track object with one artist and one album.

    Args:
        track_id (str): The Spotify track ID.
        uri (str): The Spotify URI of the track.
    """

    track = {
        "id": track_id,
        "name": "Trade It All",
        "uri": uri if uri is not None else f"spotify:track:{track_id}",
        "artists": [{"id": "ar1", "name": "Cory Henry"}],
        "album": {"id": "al1", "name": "The Revival"},
    }

    return track


def _populated_db(path: Path, track_id: str = "t1") -> None:
    """Writes a cache file with one track, its artist, a playlist entry, and a liked entry.

    Args:
        path (Path): Where to write the cache file.
        track_id (str): The ID of the track to store.
    """

    connection = sqlite3.connect(path)
    create_schema(connection)
    stats = SyncStats()
    store = TrackStore(connection, stats)
    track = _track(track_id)
    store.store_track(track)

    connection.execute(
        "INSERT INTO playlists (playlist_id, name, owner_id, collaborative, snapshot_id, synced_at) "
        "VALUES ('p1', 'Chill', 'me', 0, 'snap', '2026-01-01T00:00:00+00:00')"
    )

    connection.execute(
        "INSERT INTO playlist_songs (playlist_id, position, song_id) VALUES ('p1', 3, ?)",
        (track_id,),
    )

    connection.execute(
        "INSERT INTO library_items (source_name, item_id, added_at) "
        "VALUES ('liked_songs', ?, '2026-02-01T00:00:00+00:00')",
        (track_id,),
    )

    connection.commit()
    connection.close()


# Testing the "parse_track_id" function.


def test_parse_track_id_accepts_bare_id():
    """A bare track ID is returned without surrounding spaces."""
    assert parse_track_id(" 4F2Q ", None) == "4F2Q"


def test_parse_track_id_accepts_uri():
    """A spotify:track URI gives the track ID."""
    assert parse_track_id(None, "spotify:track:4F2Q") == "4F2Q"


def test_parse_track_id_accepts_link_with_query_and_locale():
    """An open.spotify.com link gives the track ID, even with a locale and a query string."""
    assert parse_track_id(None, "https://open.spotify.com/intl-de/track/4F2Q?si=abc") == "4F2Q"


def test_parse_track_id_rejects_non_track_link():
    """A link to something other than a track is rejected."""

    with pytest.raises(ValueError):
        parse_track_id(None, "https://open.spotify.com/album/4F2Q")


def test_parse_track_id_rejects_track_link_without_id():
    """A track link with no ID after the word track is rejected."""

    with pytest.raises(ValueError):
        parse_track_id(None, "https://open.spotify.com/track")


def test_parse_track_id_rejects_both_options():
    """Giving both --track-id and --track-link is rejected."""

    with pytest.raises(ValueError):
        parse_track_id("4F2Q", "spotify:track:4F2Q")


def test_parse_track_id_rejects_no_option():
    """Giving neither option is rejected."""

    with pytest.raises(ValueError):
        parse_track_id(None, None)


# Testing the "open_read_only" function.


def test_open_read_only_rejects_missing_file(tmp_path):
    """A cache file that does not exist is reported, and no file is created."""
    missing = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError):
        open_read_only(missing)

    assert not missing.exists()


def test_open_read_only_blocks_writes(tmp_path):
    """The connection cannot change the database."""
    path = tmp_path / "cache.db"
    _populated_db(path)
    connection = open_read_only(path)

    with pytest.raises(sqlite3.OperationalError):
        connection.execute("DELETE FROM songs")

    connection.close()


# Testing the "build_track_report" function.


def test_build_track_report_unknown_track(tmp_path):
    """A track that is not stored gets a clear message."""
    path = tmp_path / "cache.db"
    _populated_db(path)
    connection = open_read_only(path)

    report = build_track_report(connection, "nope")
    connection.close()

    assert report == "No track with ID nope is stored in the cache."


def test_build_track_report_shows_every_section(tmp_path):
    """Each entity in the model has its own section, with the stored values."""
    path = tmp_path / "cache.db"
    _populated_db(path)
    connection = open_read_only(path)

    report = build_track_report(connection, "t1")
    connection.close()

    assert "Song (songs)" in report
    assert "Artists (artists, song_artists)" in report
    assert "name: Cory Henry" in report
    assert "Albums (album_songs, raw_albums" in report
    assert "Playlist Chill:" in report
    assert "position: 3" in report
    assert "Liked songs (library_items)" in report
    assert "Top tracks (top_track_rankings)" in report
    assert "(not in any stored ranking)" in report
    assert "Sources (song_sources)" in report


def test_build_track_report_marks_empty_fields(tmp_path):
    """A field with no value is shown as (empty), not left out."""
    path = tmp_path / "cache.db"
    connection = sqlite3.connect(path)
    create_schema(connection)
    stats = SyncStats()
    store = TrackStore(connection, stats)
    track = _track("t2", uri="")
    store.store_track(track)
    connection.commit()
    connection.close()
    connection = open_read_only(path)

    report = build_track_report(connection, "t2")
    connection.close()

    assert "uri: (empty)" in report


def test_build_track_report_summarises_raw_payload_by_default(tmp_path):
    """Payloads are summarised unless the full JSON is asked for."""
    path = tmp_path / "cache.db"
    _populated_db(path)
    connection = open_read_only(path)

    summary = build_track_report(connection, "t1", include_raw=False)
    full = build_track_report(connection, "t1", include_raw=True)
    connection.close()

    assert "use --raw to show it" in summary
    assert '"album"' not in summary
    assert '"album": {' in full


def test_build_track_report_shows_every_stored_optional_section(tmp_path):
    """Genre responses, parsed genres, saved albums, rankings, and shared playlists all appear."""
    path = tmp_path / "cache.db"
    connection = sqlite3.connect(path)
    create_schema(connection)
    stats = SyncStats()
    store = TrackStore(connection, stats)
    track = _track("t1")
    store.store_track(track)

    connection.execute(
        "INSERT INTO artist_genre_responses (artist_id, source, fetched_at, status, payload) "
        "VALUES ('ar1', 'musicbrainz', '2026-01-01T00:00:00+00:00', 'found', '{\"artist\": {}}')"
    )

    connection.execute(
        "INSERT INTO artist_genre_responses (artist_id, source, fetched_at, status, payload) "
        "VALUES ('ar1', 'lastfm', '2026-01-01T00:00:00+00:00', 'error', '{\"error\": 6}')"
    )

    connection.execute("INSERT INTO genres (genre_name) VALUES ('jazz')")
    connection.execute("INSERT INTO artist_genres (artist_id, genre_name) VALUES ('ar1', 'jazz')")

    connection.execute(
        "INSERT INTO library_items (source_name, item_id, added_at) "
        "VALUES ('saved_albums', 'al1', '2026-03-01T00:00:00+00:00')"
    )

    connection.execute("INSERT INTO album_songs (album_id, position, song_id) VALUES ('al1', 0, 't1')")

    connection.execute(
        "INSERT INTO top_track_rankings (time_range, position, song_id, fetched_at) "
        "VALUES ('medium_term', 0, 't1', '2026-04-01T00:00:00+00:00')"
    )

    connection.execute(
        "INSERT INTO playlists (playlist_id, name, owner_id, collaborative, snapshot_id, synced_at) "
        "VALUES ('p2', 'Shared', 'other', 1, 'snap2', '2026-01-01T00:00:00+00:00')"
    )

    connection.execute(
        "INSERT INTO playlist_songs (playlist_id, position, song_id) VALUES ('p2', 0, 't1')"
    )

    connection.commit()
    connection.close()
    connection = open_read_only(path)

    report = build_track_report(connection, "t1")
    connection.close()

    assert "genre response from musicbrainz:" in report
    assert "genre response from lastfm:" in report
    assert "status: error" in report
    assert "      jazz" in report
    assert "saved album entry:" in report
    assert "source_name: saved_albums" in report
    assert "Ranking medium_term:" in report
    assert "collaborative: yes" in report
    assert "raw copy:" in report


def test_build_track_report_explains_missing_pieces(tmp_path):
    """Missing raw copies, artists, saved albums, and sources are each stated, not skipped."""
    path = tmp_path / "cache.db"
    _populated_db(path)
    connection = sqlite3.connect(path)
    connection.execute("DELETE FROM raw_tracks")
    connection.execute("DELETE FROM song_artists")
    connection.execute("INSERT INTO album_songs (album_id, position, song_id) VALUES ('al1', 0, 't1')")
    connection.commit()
    connection.close()
    connection = open_read_only(path)

    report = build_track_report(connection, "t1")
    connection.close()

    assert "raw copy: (not stored)" in report
    assert "(no artists stored)" in report
    assert "saved album entry: (not stored)" in report
    assert "(no sources stored)" in report


def test_build_track_report_names_a_table_that_is_not_created_yet(tmp_path):
    """Cache files from before the raw tables existed get a clear message instead of an error."""
    path = tmp_path / "cache.db"
    _populated_db(path)
    connection = sqlite3.connect(path)
    connection.execute("DROP TABLE raw_tracks")
    connection.commit()
    connection.close()
    connection = open_read_only(path)

    report = build_track_report(connection, "t1")
    connection.close()

    assert "table raw_tracks does not exist yet" in report


def test_build_track_report_lists_sources(tmp_path):
    """Every source the track was read from is listed."""
    path = tmp_path / "cache.db"
    _populated_db(path)
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO song_sources (song_id, source_name) VALUES ('t1', 'liked_songs')")
    connection.commit()
    connection.close()
    connection = open_read_only(path)

    report = build_track_report(connection, "t1")
    connection.close()

    assert "  liked_songs" in report

