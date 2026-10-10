"""Calls to the Spotify Web API."""

import requests

from sgs.constants import SPOTIFY_ME_URL


def fetch_current_user(access_token: str) -> dict:
    """Fetches the profile of the logged-in Spotify user.

    Args:
        access_token (str): A valid Spotify access token.

    Returns:
        user (dict): The user profile returned by the current-user endpoint.

    Raises:
        requests.HTTPError: If Spotify rejects the request, for example with an
            expired or invalid token.
    """
    response = requests.get(
        SPOTIFY_ME_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    response.raise_for_status()
    user = response.json()

    return user
