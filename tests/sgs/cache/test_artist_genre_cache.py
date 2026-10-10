"""Module for testing artist_genre_cache.py"""

from unittest.mock import MagicMock

from sgs.constants import ARTISTS_PER_REQUEST
from sgs.spotify_cache import SpotifyCache


def _artist(artist_id, genres):
    """Builds a Spotify artist object with the given genres."""
    artist = {"id": artist_id, "name": f"Name {artist_id}", "genres": genres}

    return artist


def _add_artists(cache, artist_ids):
    """Inserts artists the way a source sync would, before genres are fetched."""
    for artist_id in artist_ids:
        cache._connection.execute(
            "INSERT INTO artists (artist_id, name) VALUES (?, ?)",
            (artist_id, f"Name {artist_id}"),
        )

    cache._connection.commit()


def _serve_artists(monkeypatch, artists_by_id):
    """Replaces get_artists with a stand-in that serves the given artists by ID."""

    def fake(artist_ids, access_token):
        served = [artists_by_id.get(artist_id) for artist_id in artist_ids]

        return served

    mock = MagicMock(side_effect=fake)
    monkeypatch.setattr("sgs.cache.artist_genre_cache.get_artists", mock)

    return mock


def _genres_of(cache, artist_id):
    """Returns the genres stored for one artist, sorted."""
    rows = cache._connection.execute(
        "SELECT genre_name FROM artist_genres WHERE artist_id = ? ORDER BY genre_name",
        (artist_id,),
    ).fetchall()

    genres = [row[0] for row in rows]

    return genres


# Testing the "sync" method from the "ArtistGenreCache" class.


def test_sync_stores_genres_per_artist(cache_path, monkeypatch):
    """Each artist keeps its own genres, and a genre shared by two artists is stored once."""
    _serve_artists(monkeypatch, {
        "a1": _artist("a1", ["dream pop", "shoegaze"]),
        "a2": _artist("a2", ["dream pop", "jazz"]),
    })

    with SpotifyCache() as cache:
        _add_artists(cache, ["a1", "a2"])
        cache.sync_artist_genres("token")

        assert _genres_of(cache, "a1") == ["dream pop", "shoegaze"]
        assert _genres_of(cache, "a2") == ["dream pop", "jazz"]

        genre_count = cache._connection.execute("SELECT COUNT(*) FROM genres").fetchone()[0]

    assert genre_count == 3


def test_sync_marks_artists_with_no_genres_as_fetched(cache_path, monkeypatch):
    """An artist with an empty genre list is stored as fetched, so it is not requested again."""
    mock = _serve_artists(monkeypatch, {"a1": _artist("a1", [])})

    with SpotifyCache() as cache:
        _add_artists(cache, ["a1"])
        cache.sync_artist_genres("token")
        cache.sync_artist_genres("token")

        fetched_at = cache._connection.execute(
            "SELECT genres_fetched_at FROM artists WHERE artist_id = 'a1'"
        ).fetchone()[0]
        genres = _genres_of(cache, "a1")

    assert fetched_at is not None
    assert genres == []
    assert mock.call_count == 1


def test_sync_skips_artists_already_fetched(cache_path, monkeypatch):
    """Artists whose genres were fetched earlier are not requested again."""
    mock = _serve_artists(monkeypatch, {"a1": _artist("a1", ["jazz"])})

    with SpotifyCache() as cache:
        _add_artists(cache, ["a1"])
        cache.sync_artist_genres("token")
        cache.sync_artist_genres("token")

    assert mock.call_count == 1


def test_sync_leaves_unknown_artists_pending(cache_path, monkeypatch):
    """An artist Spotify does not return stays pending, so it is tried again on the next run."""
    mock = _serve_artists(monkeypatch, {})

    with SpotifyCache() as cache:
        _add_artists(cache, ["a1"])
        cache.sync_artist_genres("token")

        fetched_at = cache._connection.execute(
            "SELECT genres_fetched_at FROM artists WHERE artist_id = 'a1'"
        ).fetchone()[0]

    assert fetched_at is None
    assert mock.call_count == 1


def test_sync_splits_requests_into_batches(cache_path, monkeypatch):
    """More artists than one request allows are fetched in several batches."""
    artist_ids = [f"a{index:03d}" for index in range(ARTISTS_PER_REQUEST + 10)]
    artists_by_id = {artist_id: _artist(artist_id, ["pop"]) for artist_id in artist_ids}
    mock = _serve_artists(monkeypatch, artists_by_id)

    with SpotifyCache() as cache:
        _add_artists(cache, artist_ids)
        cache.sync_artist_genres("token")

    batch_sizes = [len(call.args[0]) for call in mock.call_args_list]
    assert batch_sizes == [ARTISTS_PER_REQUEST, 10]
