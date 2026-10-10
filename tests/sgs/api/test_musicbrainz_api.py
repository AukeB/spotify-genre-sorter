"""Module for testing musicbrainz_api.py"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from sgs.api.musicbrainz_api import _find_linked_artist_id, fetch_musicbrainz_artist


def _response(status_code, body=None):
    """Builds a fake requests.Response with the given status and JSON body."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    if status_code >= 400 and status_code != 404:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status_code} error")

    return response


def _url_lookup(musicbrainz_id):
    """Builds a URL lookup body that links a Spotify page to a MusicBrainz artist."""
    body = {
        "relations": [
            {"type": "free streaming", "artist": {"id": musicbrainz_id, "name": "Lambert"}},
        ]
    }

    return body


# Testing the "_find_linked_artist_id" function.


def test_find_linked_artist_id_returns_free_streaming_artist():
    """The artist of the free streaming relation is returned."""
    assert _find_linked_artist_id(_url_lookup("mb-1")) == "mb-1"


def test_find_linked_artist_id_returns_none_without_relation():
    """A lookup with no free streaming relation has no linked artist."""
    assert _find_linked_artist_id({"relations": [{"type": "official homepage"}]}) is None


# Testing the "fetch_musicbrainz_artist" function.


@patch("sgs.api.http.requests.get")
def test_fetch_musicbrainz_artist_returns_found_with_raw_payload(mock_get):
    """A matched artist returns both raw responses in the payload."""
    artist_body = {"id": "mb-1", "genres": [{"name": "jazz"}], "tags": []}
    mock_get.side_effect = [_response(200, _url_lookup("mb-1")), _response(200, artist_body)]

    result = fetch_musicbrainz_artist("spotify-1")

    assert result["status"] == "found"
    assert result["payload"]["url_lookup"] == _url_lookup("mb-1")
    assert result["payload"]["artist"] == artist_body
    assert mock_get.call_args_list[1].args[0].endswith("/artist/mb-1")


@patch("sgs.api.http.requests.get")
def test_fetch_musicbrainz_artist_returns_not_matched_on_404(mock_get):
    """An artist without a MusicBrainz link is reported as not matched, not as an error."""
    mock_get.return_value = _response(404)

    result = fetch_musicbrainz_artist("spotify-1")

    assert result["status"] == "not_matched"
    assert result["payload"] == {"url_lookup": None, "artist": None}
    assert mock_get.call_count == 1


@patch("sgs.api.http.requests.get")
def test_fetch_musicbrainz_artist_returns_not_matched_without_relation(mock_get):
    """A lookup that comes back without a linked artist is reported as not matched."""
    lookup = {"relations": []}
    mock_get.return_value = _response(200, lookup)

    result = fetch_musicbrainz_artist("spotify-1")

    assert result["status"] == "not_matched"
    assert result["payload"]["url_lookup"] == lookup
    assert mock_get.call_count == 1


@patch("sgs.api.http.requests.get")
def test_fetch_musicbrainz_artist_raises_on_server_error(mock_get):
    """A server error on the URL lookup is raised, so the run can be retried later."""
    mock_get.return_value = _response(500)

    with pytest.raises(requests.HTTPError):
        fetch_musicbrainz_artist("spotify-1")


@patch("sgs.api.http.requests.get")
def test_fetch_musicbrainz_artist_raises_on_artist_request_error(mock_get):
    """A server error on the artist request is raised."""
    mock_get.side_effect = [_response(200, _url_lookup("mb-1")), _response(500)]

    with pytest.raises(requests.HTTPError):
        fetch_musicbrainz_artist("spotify-1")
