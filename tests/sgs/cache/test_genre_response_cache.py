"""Module for testing genre_response_cache.py"""

import json
from unittest.mock import MagicMock

import pytest

from sgs.errors import LastfmInvalidKeyError
from sgs.spotify_cache import SpotifyCache


def _add_artists(cache, artists):
    """Inserts artists the way a source sync would, before genre responses are fetched."""
    for artist_id, name in artists:
        cache._connection.execute(
            "INSERT INTO artists (artist_id, name) VALUES (?, ?)",
            (artist_id, name),
        )

    cache._connection.commit()


def _stored(cache):
    """Returns every stored response as (artist_id, source, status, payload) tuples."""
    rows = cache._connection.execute(
        "SELECT artist_id, source, status, payload FROM artist_genre_responses ORDER BY artist_id, source"
    ).fetchall()

    return rows


def _stub_sources(monkeypatch, musicbrainz=None, lastfm=None):
    """Replaces both source clients with stand-ins and returns them."""
    mb_mock = MagicMock(side_effect=musicbrainz)
    lastfm_mock = MagicMock(side_effect=lastfm)
    monkeypatch.setattr("sgs.cache.genre_response_cache.fetch_musicbrainz_artist", mb_mock)
    monkeypatch.setattr("sgs.cache.genre_response_cache.fetch_lastfm_top_tags", lastfm_mock)

    return mb_mock, lastfm_mock


def _found(artist_id):
    """A fake MusicBrainz result for an artist."""
    result = {"status": "found", "payload": {"artist": {"id": artist_id, "genres": []}}}

    return result


def _tags(name, api_key):
    """A fake Last.fm result for an artist name."""
    result = {"status": "found", "payload": {"toptags": {"tag": [], "@attr": {"artist": name}}}}

    return result


# Testing the "sync" method from the "GenreResponseCache" class.


def test_sync_stores_both_sources_as_raw_json(cache_path, monkeypatch):
    """Each source's response is stored as JSON, one row per artist and source."""
    _stub_sources(monkeypatch, musicbrainz=_found, lastfm=_tags)

    with SpotifyCache() as cache:
        _add_artists(cache, [("a1", "Lambert")])
        cache.sync_genre_responses("key-123")
        rows = _stored(cache)

    assert [(row[0], row[1], row[2]) for row in rows] == [("a1", "lastfm", "found"), ("a1", "musicbrainz", "found")]
    musicbrainz_payload = json.loads(rows[1][3])
    assert musicbrainz_payload["artist"]["id"] == "a1"


def test_sync_skips_artists_that_already_have_a_response(cache_path, monkeypatch):
    """A source is not asked again for an artist it already answered."""
    mb_mock, lastfm_mock = _stub_sources(monkeypatch, musicbrainz=_found, lastfm=_tags)

    with SpotifyCache() as cache:
        _add_artists(cache, [("a1", "Lambert")])
        cache.sync_genre_responses("key-123")
        cache.sync_genre_responses("key-123")

    assert mb_mock.call_count == 1
    assert lastfm_mock.call_count == 1


def test_sync_skips_lastfm_without_api_key(cache_path, monkeypatch):
    """Without a Last.fm key, only MusicBrainz is requested."""
    mb_mock, lastfm_mock = _stub_sources(monkeypatch, musicbrainz=_found, lastfm=_tags)

    with SpotifyCache() as cache:
        _add_artists(cache, [("a1", "Lambert")])
        cache.sync_genre_responses(None)
        rows = _stored(cache)

    assert mb_mock.call_count == 1
    assert lastfm_mock.call_count == 0
    assert [row[1] for row in rows] == ["musicbrainz"]


def test_sync_keeps_responses_stored_before_an_error(cache_path, monkeypatch):
    """When a request fails, the responses already stored are kept for the next run."""

    def musicbrainz(artist_id):
        if artist_id == "a2":
            raise RuntimeError("network down")
        result = _found(artist_id)

        return result

    _stub_sources(monkeypatch, musicbrainz=musicbrainz, lastfm=_tags)

    with SpotifyCache() as cache:
        _add_artists(cache, [("a1", "One"), ("a2", "Two")])

        with pytest.raises(RuntimeError):
            cache.sync_genre_responses(None)

        rows = _stored(cache)

    assert [row[0] for row in rows] == ["a1"]


def test_sync_aborts_on_invalid_lastfm_key_without_storing_errors(cache_path, monkeypatch):
    """A rejected Last.fm key stops the run and stores nothing for Last.fm."""

    def rejected(name, api_key):
        raise LastfmInvalidKeyError("Last.fm rejected the API key")

    _stub_sources(monkeypatch, musicbrainz=_found, lastfm=rejected)

    with SpotifyCache() as cache:
        _add_artists(cache, [("a1", "Lambert"), ("a2", "Two")])

        with pytest.raises(LastfmInvalidKeyError):
            cache.sync_genre_responses("wrong-key")

        rows = _stored(cache)

    assert [row[1] for row in rows] == ["musicbrainz", "musicbrainz"]

