"""Module for testing lastfm_api.py"""

from unittest.mock import MagicMock, patch

import pytest

from sgs.api.lastfm_api import fetch_lastfm_top_tags
from sgs.errors import LastfmInvalidKeyError, RetryableApiError


def _response(body):
    """Builds a fake requests.Response with the given JSON body."""
    response = MagicMock()
    response.json.return_value = body

    return response


# Testing the "fetch_lastfm_top_tags" function.


@patch("sgs.api.http.requests.get")
def test_fetch_lastfm_top_tags_returns_found_with_raw_payload(mock_get):
    """A successful response is returned as found, with the body unchanged."""
    body = {"toptags": {"tag": [{"name": "jazz", "count": 100}], "@attr": {"artist": "Lambert"}}}
    mock_get.return_value = _response(body)

    result = fetch_lastfm_top_tags("Lambert", "key-123")

    assert result == {"status": "found", "payload": body}
    assert mock_get.call_args.kwargs["params"]["artist"] == "Lambert"
    assert mock_get.call_args.kwargs["params"]["api_key"] == "key-123"


@patch("sgs.api.http.requests.get")
def test_fetch_lastfm_top_tags_returns_error_for_error_body(mock_get):
    """A response with an error body is reported as an error, with the body kept."""
    body = {"error": 6, "message": "Artist not found"}
    mock_get.return_value = _response(body)

    result = fetch_lastfm_top_tags("Nobody", "key-123")

    assert result == {"status": "error", "payload": body}


@patch("sgs.api.http.requests.get")
def test_fetch_lastfm_top_tags_raises_on_invalid_key(mock_get):
    """A rejected API key raises, instead of being stored as an error for the artist."""
    mock_get.return_value = _response({"error": 10, "message": "Invalid API key"})

    with pytest.raises(LastfmInvalidKeyError):
        fetch_lastfm_top_tags("Lambert", "wrong-key")


@patch("sgs.api.http.requests.get")
def test_fetch_lastfm_top_tags_raises_on_rate_limit_body(mock_get):
    """A rate-limit error in the body raises RetryableApiError, so the request is retried."""
    mock_get.return_value = _response({"error": 29, "message": "Rate limit exceeded"})

    with pytest.raises(RetryableApiError):
        fetch_lastfm_top_tags("Lambert", "key-123")

