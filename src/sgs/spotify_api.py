"""Calls to the Spotify Web API."""

import logging
from collections.abc import Iterator

import requests

from sgs.constants import SPOTIFY_ME_URL

logger = logging.getLogger(__name__)


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


def fetch_total(url: str, access_token: str) -> int:
    """Returns how many items a paginated endpoint holds in total.

    Requests a single item, which is enough to read the `total` field.

    Args:
        url (str): The endpoint URL, such as the saved tracks endpoint.
        access_token (str): A valid Spotify access token.

    Returns:
        total (int): The total number of items on the account.

    Raises:
        requests.HTTPError: If Spotify rejects the request.
    """
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"limit": "1"},
        timeout=10,
    )

    response.raise_for_status()
    body = response.json()
    total: int = body["total"]

    return total


def get_all_pages(
    url: str,
    access_token: str,
    params: dict[str, str] | None = None,
    description: str | None = None,
) -> Iterator[dict]:
    """Yields every item from a paginated Spotify endpoint.

    Follows the `next` link until Spotify returns no further page.

    Args:
        url (str): The endpoint URL of the first page.
        access_token (str): A valid Spotify access token.
        params (dict[str, str] | None): Query parameters for the first page.
            Later pages already include them in `next`.
        description (str | None): Name used in the log messages, such as
            "playlist Chill". Defaults to the page URL when not given.

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
        items = page["items"]

        source = description or next_url
        logger.info("Read page of %d items from %s", len(items), source)

        yield from items

        next_url = page.get("next")
        next_params = None


def is_readable_playlist(
    playlist: dict,
    user_id: str,
    include_collaborative: bool,
) -> bool:
    """Checks whether Spotify allows reading the playlist's items.

    A playlist is readable when either of these is true:
    1. The logged-in user owns it.
    2. It is collaborative and include_collaborative is enabled.

    Playlists the user only follows are not readable, because Spotify returns
    403 for their items.

    Args:
        playlist (dict): A playlist object from the current-user playlists
            endpoint.
        user_id (str): The ID of the logged-in user.
        include_collaborative (bool): Whether collaborative playlists owned by
            other users should be read.

    Returns:
        readable (bool): True if the playlist meets one of the conditions above.
    """
    is_owner = playlist["owner"]["id"] == user_id
    is_collaborative = playlist["collaborative"] and include_collaborative
    readable = is_owner or is_collaborative

    return readable
