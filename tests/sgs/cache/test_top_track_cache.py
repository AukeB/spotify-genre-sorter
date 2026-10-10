"""Module for testing top_track_cache.py"""

from sgs.constants import SPOTIFY_ME_TOP_TRACKS_URL, TOP_TRACKS_SOURCE_NAME
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


def _sync_top(time_range="medium_term"):
    """Runs one top-tracks sync and returns the cached songs for the time range."""
    with SpotifyCache() as cache:
        cache.sync_top_tracks("token", time_range)
        songs = cache.get_songs_for_source(TOP_TRACKS_SOURCE_NAME)

    return songs


# Testing the "sync" method from the "TopTrackCache" class.


def test_sync_passes_configured_time_range(cache_path, spotify_calls):
    """The time range is sent as a query parameter to the top tracks endpoint."""
    calls = spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1")]})

    songs = _sync_top("long_term")

    assert calls.pages.call_args.args[0] == SPOTIFY_ME_TOP_TRACKS_URL
    assert calls.pages.call_args.kwargs["params"] == {"time_range": "long_term"}
    assert [song.id for song in songs] == ["t1"]


def test_sync_skips_request_while_ranking_is_fresh(cache_path, spotify_calls):
    """A recent ranking for the same time range is not requested from Spotify again."""
    calls = spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1")]})

    _sync_top()
    songs = _sync_top()

    assert calls.pages.call_count == 1
    assert [song.id for song in songs] == ["t1"]


def test_sync_requests_ranking_again_when_stale(cache_path, spotify_calls):
    """A ranking older than TOP_TRACKS_MAX_AGE_HOURS is requested again."""
    spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1")]})
    _sync_top()

    with SpotifyCache() as cache:
        cache._connection.execute("UPDATE top_track_rankings SET fetched_at = '2000-01-01T00:00:00+00:00'")
        cache._connection.commit()

    calls = spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1")]})
    _sync_top()

    assert calls.pages.call_count == 1


def test_sync_keeps_only_the_current_time_range_in_source(cache_path, spotify_calls):
    """Switching the time range replaces the songs shown for the top tracks source."""
    spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1")]})
    _sync_top("medium_term")

    spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t2")]})
    songs = _sync_top("long_term")

    assert [song.id for song in songs] == ["t2"]


def test_sync_skips_null_entries(cache_path, spotify_calls):
    """Null entries in the top tracks response are not stored."""
    spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [None, _track("t1")]})

    songs = _sync_top()

    assert [song.id for song in songs] == ["t1"]


# Testing the "sync" method with refresh from the "TopTrackCache" class.


def test_sync_with_refresh_requests_fresh_ranking_again(cache_path, spotify_calls):
    """With refresh, a ranking that is still fresh is requested from Spotify again."""
    calls = spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1")]})
    _sync_top()

    with SpotifyCache() as cache:
        cache.sync_top_tracks("token", "medium_term", refresh=True)

    assert calls.pages.call_count == 2
