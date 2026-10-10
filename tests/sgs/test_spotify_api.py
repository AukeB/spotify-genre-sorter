"""Module for testing spotify_api.py"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from sgs.constants import SPOTIFY_ME_URL
from sgs.spotify_api import fetch_current_user, fetch_total, get_all_pages, get_artists


# Testing the "fetch_current_user" function.


@patch("sgs.spotify_api.requests.get")
def test_fetch_current_user_returns_profile(mock_get):
    """The profile from the current-user endpoint is returned."""
    response = MagicMock()
    response.json.return_value = {"display_name": "Test User"}
    mock_get.return_value = response

    user = fetch_current_user("token-123")

    assert user == {"display_name": "Test User"}
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == SPOTIFY_ME_URL
    assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer token-123"}


@patch("sgs.spotify_api.requests.get")
def test_fetch_current_user_raises_on_rejected_token(mock_get):
    """A rejected token raises requests.HTTPError."""
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
    mock_get.return_value = response

    with pytest.raises(requests.HTTPError):
        fetch_current_user("bad-token")


# Testing the "get_all_pages" function.


@patch("sgs.spotify_api.requests.get")
def test_get_all_pages_follows_next_links(mock_get):
    """Items from every page are yielded, following the next link until it is null."""
    first_page = MagicMock()
    first_page.json.return_value = {"items": [1, 2], "next": "https://next-page"}
    second_page = MagicMock()
    second_page.json.return_value = {"items": [3], "next": None}
    mock_get.side_effect = [first_page, second_page]

    items = list(get_all_pages("https://api.example/items", "token-123", params={"limit": "2"}))

    assert items == [1, 2, 3]
    assert mock_get.call_args_list[0].args[0] == "https://api.example/items"
    assert mock_get.call_args_list[0].kwargs["params"] == {"limit": "2"}
    assert mock_get.call_args_list[1].args[0] == "https://next-page"
    assert mock_get.call_args_list[1].kwargs["params"] is None


@patch("sgs.spotify_api.requests.get")
def test_get_all_pages_raises_on_error(mock_get):
    """A failed page request raises requests.HTTPError."""
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("429 Too Many Requests")
    mock_get.return_value = response

    with pytest.raises(requests.HTTPError):
        list(get_all_pages("https://api.example/items", "token-123"))


# Testing the "fetch_total" function.


@patch("sgs.spotify_api.requests.get")
def test_fetch_total_returns_total_from_single_item_request(mock_get):
    """Only one item is requested, and the total field is returned."""
    response = MagicMock()
    response.json.return_value = {"total": 1234, "items": [{"id": "x"}]}
    mock_get.return_value = response

    total = fetch_total("https://api.example/items", "token-123")

    assert total == 1234
    assert mock_get.call_args.kwargs["params"] == {"limit": "1"}
    assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer token-123"}


@patch("sgs.spotify_api.requests.get")
def test_fetch_total_raises_on_error(mock_get):
    """A rejected request raises requests.HTTPError."""
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
    mock_get.return_value = response

    with pytest.raises(requests.HTTPError):
        fetch_total("https://api.example/items", "bad-token")


# Testing the "get_artists" function.


@patch("sgs.spotify_api.requests.get")
def test_get_artists_sends_ids_in_one_request(mock_get):
    """The IDs are joined into one request, and the artists keep their order, with None for unknown IDs."""
    response = MagicMock()
    response.json.return_value = {"artists": [{"id": "a1", "genres": []}, None]}
    mock_get.return_value = response

    artists = get_artists(["a1", "a2"], "token-123")

    assert artists == [{"id": "a1", "genres": []}, None]
    assert mock_get.call_count == 1
    assert mock_get.call_args.kwargs["params"] == {"ids": "a1,a2"}
    assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer token-123"}


@patch("sgs.spotify_api.requests.get")
def test_get_artists_raises_on_error(mock_get):
    """A rejected request raises requests.HTTPError."""
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
    mock_get.return_value = response

    with pytest.raises(requests.HTTPError):
        get_artists(["a1"], "bad-token")
