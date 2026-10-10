"""Helper functions for the Spotify login: PKCE values and token parsing.

PKCE (Proof Key for Code Exchange) is an extension to the OAuth authorization
code flow that protects the login for apps that cannot keep a client secret. The
app sends a secret random verifier only at token exchange, and a hash of it (the
challenge) at login, so an intercepted authorization code is useless without the
verifier.
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import requests

from sgs.authentication.token_model import TokenInfo
from sgs.errors import SpotifyAuthError


def generate_pkce_pair() -> tuple[str, str]:
    """Creates a PKCE code verifier and its S256 code challenge.

    Returns:
        code_verifier, code_challenge (tuple[str, str]): The code verifier and
            the code challenge.
    """
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return code_verifier, code_challenge


def generate_state() -> str:
    """Creates a random state value to protect the login against forgery.

    Returns:
        state (str): A random URL-safe string.
    """
    state = secrets.token_urlsafe(16)

    return state


def parse_token_response(
    response: requests.Response,
    previous_refresh_token: str | None = None,
) -> TokenInfo:
    """Converts a token endpoint response into a TokenInfo.

    Args:
        response (requests.Response): The response from the token endpoint.
        previous_refresh_token (str | None): Kept if the response has no new
            one.

    Returns:
        token (TokenInfo): The parsed token.

    Raises:
        SpotifyAuthError: If the response is not successful.
    """
    if response.status_code != 200:
        raise SpotifyAuthError(
            f"Token request failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
    token = TokenInfo(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token") or previous_refresh_token,
        expires_at=expires_at,
        scope=data.get("scope", ""),
    )

    return token
