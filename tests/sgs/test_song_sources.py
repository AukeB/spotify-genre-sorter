"""Module for testing song_sources.py"""

from unittest.mock import patch

from sgs.config.config_model import ConfigModel
from sgs.constants import SPOTIFY_API_BASE_URL, SPOTIFY_ME_ALBUMS_URL, SPOTIFY_ME_PLAYLISTS_URL, SPOTIFY_ME_TOP_TRACKS_URL, SPOTIFY_ME_TRACKS_URL
from sgs.song_sources import SongSources

ADDED_AT = "2026-01-01T00:00:00+00:00"


def _config(liked=False, albums=False, top=False, playlists=False, time_range="medium_term", collaborative=True):
    """Builds a ConfigModel with the given sources and options."""
    data = {
        "sources": {
            "liked_songs": liked,
            "saved_albums": albums,
            "top_tracks": top,
            "your_playlists": playlists,
        },
        "options": {
            "top_tracks_time_range": time_range,
            "include_collaborative_playlists": collaborative,
        },
    }

    config = ConfigModel.model_validate(data)

    return config


def _track(track_id):
    """Builds a Spotify track object."""
    track = {
        "id": track_id,
        "name": f"Song {track_id}",
        "uri": f"spotify:track:{track_id}",
        "type": "track",
        "artists": [{"id": "artist-1", "name": "Artist 1"}],
    }

    return track


def _playlist_responses():
    """Playlists owned by me, followed from someone else, and collaborative with someone else."""
    responses = {
        SPOTIFY_ME_PLAYLISTS_URL: [
            {"id": "p1", "name": "P1", "snapshot_id": "s1", "owner": {"id": "me"}, "collaborative": False},
            {"id": "p2", "name": "P2", "snapshot_id": "s2", "owner": {"id": "other"}, "collaborative": False},
            {"id": "p3", "name": "P3", "snapshot_id": "s3", "owner": {"id": "other"}, "collaborative": True},
        ],
        f"{SPOTIFY_API_BASE_URL}/playlists/p1/items": [
            {"item": _track("t1")},
            {"item": None},
            {"is_local": True, "item": _track("local")},
            {"item": {**_track("episode"), "type": "episode"}},
        ],
        f"{SPOTIFY_API_BASE_URL}/playlists/p3/items": [{"item": _track("t3")}],
    }

    return responses


# Testing the "_fetch_liked_songs" method from the "SongSources" class.


def test_liked_songs_skips_unavailable_tracks(cache_path, spotify_calls):
    """Null tracks are skipped and the rest are tagged with the liked_songs source."""
    spotify_calls({
        SPOTIFY_ME_TRACKS_URL: [
            {"added_at": ADDED_AT, "track": _track("t1")},
            {"added_at": ADDED_AT, "track": None},
            {"added_at": ADDED_AT, "track": _track("t2")},
        ]
    })

    songs = SongSources(_config(liked=True), "token").get_all_songs()

    assert [song.id for song in songs] == ["t1", "t2"]
    assert all(song.sources == {"liked_songs"} for song in songs)


# Testing the "_fetch_saved_albums" method from the "SongSources" class.


def test_saved_albums_reads_every_album_track(cache_path, spotify_calls):
    """Tracks come from each saved album's own track list."""
    spotify_calls({
        SPOTIFY_ME_ALBUMS_URL: [{"added_at": ADDED_AT, "album": {"id": "a1", "name": "Album 1"}}],
        f"{SPOTIFY_API_BASE_URL}/albums/a1/tracks": [_track("t1"), _track("t2")],
    })

    songs = SongSources(_config(albums=True), "token").get_all_songs()

    assert [song.id for song in songs] == ["t1", "t2"]
    assert all(song.sources == {"saved_albums"} for song in songs)


# Testing the "_fetch_top_tracks" method from the "SongSources" class.


def test_top_tracks_passes_configured_time_range(cache_path, spotify_calls):
    """The configured time range is sent as a query parameter."""
    calls = spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1")]})

    songs = SongSources(_config(top=True, time_range="long_term"), "token").get_all_songs()

    assert calls.pages.call_args.kwargs["params"] == {"time_range": "long_term"}
    assert songs[0].sources == {"top_tracks"}


# Testing the "_fetch_your_playlists" method from the "SongSources" class.


def test_playlists_only_reads_owned_playlists_when_collaborative_disabled(cache_path, spotify_calls):
    """Followed playlists are never read. Collaborative playlists are read only when enabled."""
    spotify_calls(_playlist_responses())

    with patch("sgs.song_sources.fetch_current_user", return_value={"id": "me"}):
        songs = SongSources(_config(playlists=True, collaborative=False), "token").get_all_songs()

    assert [song.id for song in songs] == ["t1"]
    assert songs[0].sources == {"your_playlists"}


def test_playlists_reads_collaborative_playlists_when_enabled(cache_path, spotify_calls):
    """Collaborative playlists owned by others are read when enabled. Skips null, local, and episode items."""
    spotify_calls(_playlist_responses())

    with patch("sgs.song_sources.fetch_current_user", return_value={"id": "me"}):
        songs = SongSources(_config(playlists=True, collaborative=True), "token").get_all_songs()

    assert sorted(song.id for song in songs) == ["t1", "t3"]


# Testing the "get_all_songs" method from the "SongSources" class.


def test_get_all_songs_skips_disabled_sources(cache_path, spotify_calls):
    """Only sources set to true are requested from Spotify."""
    calls = spotify_calls({SPOTIFY_ME_TOP_TRACKS_URL: []})

    SongSources(_config(top=True), "token").get_all_songs()

    requested_urls = [call.args[0] for call in calls.pages.call_args_list]
    assert requested_urls == [SPOTIFY_ME_TOP_TRACKS_URL]


def test_get_all_songs_merges_duplicate_tracks_by_id(cache_path, spotify_calls):
    """A track found in two sources appears once with both sources. Different track IDs stay separate."""
    spotify_calls({
        SPOTIFY_ME_TRACKS_URL: [{"added_at": ADDED_AT, "track": _track("t1")}],
        SPOTIFY_ME_TOP_TRACKS_URL: [_track("t1"), _track("t2")],
    })

    songs = SongSources(_config(liked=True, top=True), "token").get_all_songs()

    by_id = {song.id: song for song in songs}
    assert set(by_id) == {"t1", "t2"}
    assert by_id["t1"].sources == {"liked_songs", "top_tracks"}
    assert by_id["t2"].sources == {"top_tracks"}
