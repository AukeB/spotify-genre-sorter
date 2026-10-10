"""Module for testing playlist_cache.py"""

import logging

from sgs.constants import PLAYLIST_SOURCE_NAME, SPOTIFY_API_BASE_URL, SPOTIFY_ME_PLAYLISTS_URL
from sgs.spotify_cache import SpotifyCache


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


def _responses(playlists, items_by_playlist):
    """Builds the responses for the playlists endpoint and each playlist's items."""
    responses = {SPOTIFY_ME_PLAYLISTS_URL: playlists}

    for playlist_id, items in items_by_playlist.items():
        responses[f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}/items"] = items

    return responses


def _sync(access_token="token", user_id="me", include_collaborative=False):
    """Runs one playlist sync on a cache and returns the cached songs."""
    with SpotifyCache() as cache:
        cache.sync_playlists(access_token, user_id=user_id, include_collaborative=include_collaborative)
        songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

    return songs


# Testing the "sync" method from the "PlaylistCache" class.


def test_sync_stores_songs_in_playlist_order(cache_path, spotify_calls):
    """Songs are stored with their playlist position, and artists keep their credit order."""
    items = {"p1": [{"item": _track("t1", ("a1", "a2"))}, {"item": _track("t2")}]}
    spotify_calls(_responses([_playlist("p1")], items))

    songs = _sync()

    assert [song.id for song in songs] == ["t1", "t2"]
    assert songs[0].artist_ids == ["a1", "a2"]
    assert songs[0].sources == {PLAYLIST_SOURCE_NAME}


def test_sync_skips_tracks_without_id(cache_path, spotify_calls):
    """Items without a track ID are not stored, and the remaining songs keep their order."""
    items = {"p1": [{"item": {**_track("t1"), "id": None}}, {"item": _track("t2")}]}
    spotify_calls(_responses([_playlist("p1")], items))

    songs = _sync()

    assert [song.id for song in songs] == ["t2"]


def test_sync_skips_unchanged_playlist(cache_path, spotify_calls):
    """A playlist whose snapshot_id is unchanged is not read from Spotify again."""
    calls = spotify_calls(_responses([_playlist("p1", snapshot_id="s1")], {"p1": [{"item": _track("t1")}]}))

    _sync()
    _sync()

    item_requests = [call for call in calls.pages.call_args_list if "/items" in call.args[0]]
    assert len(item_requests) == 1


def test_sync_rereads_playlist_when_snapshot_changes(cache_path, spotify_calls):
    """A changed snapshot_id replaces the playlist's songs with the new ones."""
    spotify_calls(_responses([_playlist("p1", "s1")], {"p1": [{"item": _track("t1")}]}))
    _sync()

    spotify_calls(_responses([_playlist("p1", "s2")], {"p1": [{"item": _track("t2")}]}))
    songs = _sync()

    assert [song.id for song in songs] == ["t2"]


def test_sync_removes_playlists_no_longer_readable(cache_path, spotify_calls):
    """Playlists that disappear or become unreadable are removed from the cache."""
    items = {"p1": [{"item": _track("t1")}], "p2": [{"item": _track("t2")}]}
    spotify_calls(_responses([_playlist("p1"), _playlist("p2")], items))
    _sync()

    spotify_calls(_responses([_playlist("p1")], items))
    songs = _sync()

    assert [song.id for song in songs] == ["t1"]


def test_sync_skips_followed_playlists(cache_path, spotify_calls):
    """Playlists owned by someone else are not cached when collaborative is off."""
    items = {"p1": [{"item": _track("t1")}]}
    spotify_calls(_responses([_playlist("p1", owner="other", collaborative=False)], items))

    songs = _sync(include_collaborative=True)

    assert songs == []


def test_sync_counts_changed_song_and_artist_names(cache_path, spotify_calls, caplog):
    """A song or artist whose name changed is counted as changed in the sync summary."""
    first_track = _track("t1")
    first_track["artists"] = [{"id": "a1", "name": "Old Artist"}]
    first_track["name"] = "Old Song"

    second_track = _track("t1")
    second_track["artists"] = [{"id": "a1", "name": "New Artist"}]
    second_track["name"] = "New Song"

    spotify_calls(_responses([_playlist("p1", "s1")], {"p1": [{"item": first_track}]}))
    _sync()

    caplog.set_level(logging.INFO)
    spotify_calls(_responses([_playlist("p1", "s2")], {"p1": [{"item": second_track}]}))
    _sync()

    changed_lines = [record.getMessage() for record in caplog.records if "changed" in record.getMessage()]
    assert "'songs': 1" in changed_lines[0]
    assert "'artists': 1" in changed_lines[0]


# Testing the "sync" method with refresh from the "PlaylistCache" class.


def test_sync_with_refresh_reads_unchanged_playlist_again(cache_path, spotify_calls):
    """With refresh, a playlist whose snapshot did not change is read from Spotify again."""
    calls = spotify_calls(_responses([_playlist("p1", "s1")], {"p1": [{"item": _track("t1")}]}))
    _sync()

    with SpotifyCache() as cache:
        cache.sync_playlists("token", user_id="me", include_collaborative=False, refresh=True)

    item_requests = [call for call in calls.pages.call_args_list if "/items" in call.args[0]]
    assert len(item_requests) == 2
