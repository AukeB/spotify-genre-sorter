"""Module for testing spotify_cache.py"""

import logging
import sqlite3
from unittest.mock import patch

from sgs.constants import SPOTIFY_ME_PLAYLISTS_URL
from sgs.spotify_cache import PLAYLIST_SOURCE_NAME, SpotifyCache


def _track(track_id, artist_ids=("artist-1",)):
    """Builds a Spotify track object with the given artists."""
    track = {
        "id": track_id,
        "name": f"Song {track_id}",
        "uri": f"spotify:track:{track_id}",
        "type": "track",
        "artists": [{"id": artist_id, "name": f"Name {artist_id}"} for artist_id in artist_ids],
    }

    return track


def _playlist(playlist_id, snapshot_id="s1", owner="me", collaborative=False):
    """Builds a Spotify playlist object."""
    playlist = {
        "id": playlist_id,
        "name": f"Playlist {playlist_id}",
        "snapshot_id": snapshot_id,
        "owner": {"id": owner},
        "collaborative": collaborative,
    }

    return playlist


def _fake_spotify(playlists, items_by_playlist):
    """Returns a stand-in for get_all_pages that serves playlists and items."""

    def fake(url, access_token, params=None, description=None):
        if url == SPOTIFY_ME_PLAYLISTS_URL:
            result = list(playlists)
        else:
            playlist_id = url.split("/playlists/")[1].split("/")[0]
            result = list(items_by_playlist.get(playlist_id, []))

        return result

    return fake


# Testing the "__init__" method from the "SpotifyCache" class.


def test_init_creates_all_tables(cache_path):
    """Opening the cache creates every table in the schema."""
    with SpotifyCache() as cache:
        cache.close()

    connection = sqlite3.connect(cache_path)
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    connection.close()

    table_names = {row[0] for row in rows}
    assert table_names >= {
        "songs",
        "artists",
        "genres",
        "artist_genres",
        "song_artists",
        "playlists",
        "playlist_songs",
        "song_sources",
    }


# Testing the "sync_playlists" method from the "SpotifyCache" class.


def test_sync_playlists_stores_songs_in_playlist_order(cache_path):
    """Songs are stored with their playlist position, and artists keep their credit order."""
    playlists = [_playlist("p1")]
    items = {"p1": [{"item": _track("t1", ("a1", "a2"))}, {"item": _track("t2")}]}

    with patch("sgs.spotify_cache.get_all_pages", side_effect=_fake_spotify(playlists, items)):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)
            songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    assert [song.id for song in songs] == ["t1", "t2"]
    assert songs[0].artist_ids == ["a1", "a2"]
    assert songs[0].sources == {PLAYLIST_SOURCE_NAME}


def test_sync_playlists_skips_tracks_without_id(cache_path):
    """Items without a track ID are not stored, and the remaining songs keep their order."""
    playlists = [_playlist("p1")]
    items = {
        "p1": [
            {"item": {**_track("t1"), "id": None}},
            {"item": _track("t2")},
        ]
    }

    with patch("sgs.spotify_cache.get_all_pages", side_effect=_fake_spotify(playlists, items)):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)
            songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    assert [song.id for song in songs] == ["t2"]


def test_sync_playlists_counts_changed_song_and_artist_names(cache_path, caplog):
    """A song or artist whose name changed is counted as changed in the sync summary."""
    first_track = _track("t1")
    first_track["artists"] = [{"id": "a1", "name": "Old Artist"}]
    first_track["name"] = "Old Song"

    second_track = _track("t1")
    second_track["artists"] = [{"id": "a1", "name": "New Artist"}]
    second_track["name"] = "New Song"

    with patch(
        "sgs.spotify_cache.get_all_pages",
        side_effect=_fake_spotify([_playlist("p1", "s1")], {"p1": [{"item": first_track}]}),
    ):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)

    caplog.set_level(logging.INFO, logger="sgs.spotify_cache")

    with patch(
        "sgs.spotify_cache.get_all_pages",
        side_effect=_fake_spotify([_playlist("p1", "s2")], {"p1": [{"item": second_track}]}),
    ):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)

    changed_lines = [record.getMessage() for record in caplog.records if "changed" in record.getMessage()]
    assert "'songs': 1" in changed_lines[0]
    assert "'artists': 1" in changed_lines[0]


def test_sync_playlists_skips_unchanged_playlist(cache_path):
    """A playlist whose snapshot_id is unchanged is not read from Spotify again."""
    playlists = [_playlist("p1", snapshot_id="s1")]
    items = {"p1": [{"item": _track("t1")}]}
    fake = _fake_spotify(playlists, items)

    with patch("sgs.spotify_cache.get_all_pages", side_effect=fake) as mock:
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)
            cache.sync_playlists("token", user_id="me", include_collaborative=False)

    requested_urls = [call.args[0] for call in mock.call_args_list]
    item_requests = [url for url in requested_urls if "/items" in url]
    assert len(item_requests) == 1


def test_sync_playlists_rereads_playlist_when_snapshot_changes(cache_path):
    """A changed snapshot_id replaces the playlist's songs with the new ones."""
    first_items = {"p1": [{"item": _track("t1")}]}
    second_items = {"p1": [{"item": _track("t2")}]}

    with patch(
        "sgs.spotify_cache.get_all_pages",
        side_effect=_fake_spotify([_playlist("p1", "s1")], first_items),
    ):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)

    with patch(
        "sgs.spotify_cache.get_all_pages",
        side_effect=_fake_spotify([_playlist("p1", "s2")], second_items),
    ):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)
            songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    assert [song.id for song in songs] == ["t2"]


def test_sync_playlists_removes_playlists_no_longer_readable(cache_path):
    """Playlists that disappear or become unreadable are removed from the cache."""
    all_playlists = [_playlist("p1"), _playlist("p2")]
    items = {"p1": [{"item": _track("t1")}], "p2": [{"item": _track("t2")}]}

    with patch(
        "sgs.spotify_cache.get_all_pages",
        side_effect=_fake_spotify(all_playlists, items),
    ):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)

    with patch(
        "sgs.spotify_cache.get_all_pages",
        side_effect=_fake_spotify([_playlist("p1")], items),
    ):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=False)
            songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    assert [song.id for song in songs] == ["t1"]


def test_sync_playlists_skips_followed_playlists(cache_path):
    """Playlists owned by someone else are not cached when collaborative is off."""
    playlists = [_playlist("p1", owner="other", collaborative=False)]
    items = {"p1": [{"item": _track("t1")}]}

    with patch("sgs.spotify_cache.get_all_pages", side_effect=_fake_spotify(playlists, items)):
        with SpotifyCache() as cache:
            cache.sync_playlists("token", user_id="me", include_collaborative=True)
            songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    assert songs == []


# Testing the "get_songs_for_source" method from the "SpotifyCache" class.


def test_get_songs_for_source_returns_only_requested_source(cache_path):
    """Songs from other sources are not returned."""
    with SpotifyCache() as cache:
        cache._connection.execute(
            "INSERT INTO songs (song_id, name, uri) VALUES ('t1', 'Song', 'uri')"
        )
        cache._connection.execute(
            "INSERT INTO song_sources (song_id, source_name) VALUES ('t1', 'liked_songs')"
        )
        songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    assert songs == []
