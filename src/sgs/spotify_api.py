"""Calls to the Spotify Web API."""

from collections.abc import Iterator

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


def get_all_pages(
    url: str,
    access_token: str,
    params: dict[str, str] | None = None,
) -> Iterator[dict]:
    """Yields every item from a paginated Spotify endpoint.

    Follows the `next` link until Spotify returns no further page.

    Args:
        url (str): The endpoint URL of the first page.
        access_token (str): A valid Spotify access token.
        params (dict[str, str] | None): Query parameters for the first page.
            Later pages already include them in `next`.

    Yields:
        dict: One item from the `items` list of each page.

    Raises:
        requests.HTTPError: If Spotify rejects any of the requests.
    """
    next_url = url
    next_params = params

    while next_url is not None:
        response = requests.get(
            next_url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=next_params,
            timeout=10,
        )

        response.raise_for_status()
        page = response.json()

        yield from page["items"]

        next_url = page.get("next")
        next_params = None
