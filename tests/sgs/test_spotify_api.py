"""Module for testing spotify_api.py"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from sgs.constants import SPOTIFY_ME_URL
from sgs.spotify_api import fetch_current_user


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
