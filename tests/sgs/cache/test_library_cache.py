"""Module for testing library_cache.py"""

import sqlite3

import pytest

from sgs.cache.library_cache import LibraryCache
from sgs.cache.source_links import SourceLinks
from sgs.cache.sync_stats import SyncStats
from sgs.cache.track_store import TrackStore
from sgs.constants import (
    LIKED_SOURCE_NAME,
    SAVED_ALBUMS_SOURCE_NAME,
    SPOTIFY_API_BASE_URL,
    SPOTIFY_ME_ALBUMS_URL,
    SPOTIFY_ME_TRACKS_URL,
)

from sgs.spotify_cache import SpotifyCache


def _track(track_id):
    """Builds a Spotify track object."""
    track = {
        "id": track_id,
        "name": f"Song {track_id}",
        "uri": f"spotify:track:{track_id}",
        "type": "track",
        "artists": [{"id": "artist-1", "name": "Name artist-1"}],
    }

    return track


def _saved(track_id, added_at):
    """Builds a saved-track item as returned by the saved tracks endpoint."""
    item = {"added_at": added_at, "track": _track(track_id)}

    return item


def _saved_album(album_id, added_at):
    """Builds a saved-album item as returned by the saved albums endpoint."""
    item = {"added_at": added_at, "album": {"id": album_id, "name": f"Album {album_id}"}}

    return item


def _sync_liked(access_token="token"):
    """Runs one liked-songs sync and returns the cached songs."""
    with SpotifyCache() as cache:
        cache.sync_liked_songs(access_token)
        songs = cache.get_songs_for_source(LIKED_SOURCE_NAME)

    return songs


def _sync_albums(access_token="token"):
    """Runs one saved-albums sync and returns the cached songs."""
    with SpotifyCache() as cache:
        cache.sync_saved_albums(access_token)
        songs = cache.get_songs_for_source(SAVED_ALBUMS_SOURCE_NAME)

    return songs


# Testing the "sync" method from the "LikedSongsCache" class.


def test_liked_songs_reads_only_new_items_on_second_run(cache_path, spotify_calls):
    """Only the tracks added since the last run are stored, and the first run stores all."""
    responses = {SPOTIFY_ME_TRACKS_URL: [_saved("t2", "2026-02-01"), _saved("t1", "2026-01-01")]}
    spotify_calls(responses)
    _sync_liked()

    responses[SPOTIFY_ME_TRACKS_URL].insert(0, _saved("t3", "2026-03-01"))
    songs = _sync_liked()

    assert sorted(song.id for song in songs) == ["t1", "t2", "t3"]


def test_liked_songs_removes_tracks_when_total_differs(cache_path, spotify_calls):
    """A track removed from the library is detected through the total and removed from the cache."""
    responses = {SPOTIFY_ME_TRACKS_URL: [_saved("t2", "2026-02-01"), _saved("t1", "2026-01-01")]}
    spotify_calls(responses)
    _sync_liked()

    responses[SPOTIFY_ME_TRACKS_URL] = [_saved("t2", "2026-02-01")]
    songs = _sync_liked()

    assert [song.id for song in songs] == ["t2"]


def test_liked_songs_updates_track_when_added_again(cache_path, spotify_calls):
    """A track that was removed and liked again is stored with its new added_at date."""
    responses = {SPOTIFY_ME_TRACKS_URL: [_saved("t1", "2026-01-01")]}
    spotify_calls(responses)
    _sync_liked()

    responses[SPOTIFY_ME_TRACKS_URL] = [_saved("t1", "2026-06-01")]
    songs = _sync_liked()

    assert [song.id for song in songs] == ["t1"]


def test_liked_songs_full_read_stores_items_after_a_known_one(cache_path, spotify_calls):
    """When the totals differ, a full read stores items that came after the first known item."""
    responses = {SPOTIFY_ME_TRACKS_URL: [_saved("t1", "2026-01-01")]}
    spotify_calls(responses)
    _sync_liked()

    responses[SPOTIFY_ME_TRACKS_URL] = [_saved("t1", "2026-01-01"), _saved("t2", "2025-12-01")]
    songs = _sync_liked()

    assert sorted(song.id for song in songs) == ["t1", "t2"]


def test_liked_songs_skips_null_tracks(cache_path, spotify_calls):
    """Items whose track is null are not stored."""
    responses = {
        SPOTIFY_ME_TRACKS_URL: [
            {"added_at": "2026-02-01", "track": None},
            _saved("t1", "2026-01-01"),
        ]
    }

    spotify_calls(responses)

    songs = _sync_liked()

    assert [song.id for song in songs] == ["t1"]


# Testing the "sync" method from the "SavedAlbumsCache" class.


def test_saved_albums_fetches_album_tracks_only_once(cache_path, spotify_calls):
    """An album's tracks are requested once, even when the album list is read again."""
    responses = {
        SPOTIFY_ME_ALBUMS_URL: [_saved_album("a1", "2026-01-01")],
        f"{SPOTIFY_API_BASE_URL}/albums/a1/tracks": [_track("t1"), _track("t2")],
    }

    calls = spotify_calls(responses)

    _sync_albums()
    songs = _sync_albums()

    album_requests = [call for call in calls.pages.call_args_list if "/albums/a1/tracks" in call.args[0]]
    assert len(album_requests) == 1
    assert sorted(song.id for song in songs) == ["t1", "t2"]


def test_saved_albums_removes_album_songs_when_album_is_removed(cache_path, spotify_calls):
    """Removing a saved album removes its tracks from the saved albums source."""
    responses = {
        SPOTIFY_ME_ALBUMS_URL: [_saved_album("a1", "2026-01-01"), _saved_album("a2", "2026-01-02")],
        f"{SPOTIFY_API_BASE_URL}/albums/a1/tracks": [_track("t1")],
        f"{SPOTIFY_API_BASE_URL}/albums/a2/tracks": [_track("t2")],
    }

    spotify_calls(responses)
    _sync_albums()

    responses[SPOTIFY_ME_ALBUMS_URL] = [_saved_album("a2", "2026-01-02")]
    songs = _sync_albums()

    assert [song.id for song in songs] == ["t2"]


def test_saved_albums_full_read_stores_albums_after_a_known_one(cache_path, spotify_calls):
    """When the totals differ, a full read fetches albums that came after the first known one."""
    responses = {
        SPOTIFY_ME_ALBUMS_URL: [_saved_album("a1", "2026-01-01")],
        f"{SPOTIFY_API_BASE_URL}/albums/a1/tracks": [_track("t1")],
    }

    spotify_calls(responses)
    _sync_albums()

    responses[SPOTIFY_ME_ALBUMS_URL] = [_saved_album("a1", "2026-01-01"), _saved_album("a2", "2025-12-01")]
    responses[f"{SPOTIFY_API_BASE_URL}/albums/a2/tracks"] = [_track("t2")]
    songs = _sync_albums()

    assert sorted(song.id for song in songs) == ["t1", "t2"]


# Testing the "_item_id" and "_store_item" methods from the "LibraryCache" class.


def test_base_library_cache_requires_subclass_methods():
    """The base class cannot read or store an item, so subclasses must define both methods."""
    connection = sqlite3.connect(":memory:")
    stats = SyncStats()
    cache = LibraryCache(connection, stats, TrackStore(connection, stats), SourceLinks(connection, stats))

    with pytest.raises(NotImplementedError):
        cache._item_id({})

    with pytest.raises(NotImplementedError):
        cache._store_item({}, "token")

    connection.close()

