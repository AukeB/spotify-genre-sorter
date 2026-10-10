"""Module for testing authentication/utils.py"""

import base64
import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from sgs.authentication.utils import (
    generate_pkce_pair,
    generate_state,
    parse_token_response,
)
from sgs.errors import SpotifyAuthError


def _response(status_code=200, payload=None, text=""):
    """Builds a fake requests.Response."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = payload or {}
    return response


# Testing the "generate_pkce_pair" function.


def test_pkce_challenge_is_s256_of_verifier():
    """The challenge is the URL-safe base64 SHA-256 of the verifier, without padding."""
    code_verifier, code_challenge = generate_pkce_pair()

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    assert code_challenge == expected
    assert len(code_verifier) >= 43


def test_pkce_pairs_are_random():
    """Each call creates a new verifier."""
    first_verifier, _ = generate_pkce_pair()
    second_verifier, _ = generate_pkce_pair()

    assert first_verifier != second_verifier


# Testing the "generate_state" function.


def test_generate_state_is_random_and_url_safe():
    """Each state value is different and only uses URL-safe characters."""
    first_state = generate_state()
    second_state = generate_state()

    assert first_state != second_state
    assert all(char.isalnum() or char in "-_" for char in first_state)


# Testing the "parse_token_response" function.


def test_parse_token_response_success():
    """A successful response becomes a TokenInfo with the new refresh token."""
    response = _response(
        payload={
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "scope": "user-library-read",
        }
    )

    token = parse_token_response(response, previous_refresh_token="old-refresh")

    assert token.access_token == "new-access"
    assert token.refresh_token == "new-refresh"
    assert token.scope == "user-library-read"
    assert token.expires_at > datetime.now(timezone.utc)


def test_parse_token_response_keeps_previous_refresh_token():
    """When the response has no refresh token, the previous one is kept."""
    response = _response(payload={"access_token": "new-access", "expires_in": 3600})

    token = parse_token_response(response, previous_refresh_token="old-refresh")

    assert token.refresh_token == "old-refresh"
    assert token.scope == ""


def test_parse_token_response_error_status_raises():
    """A non-200 response raises SpotifyAuthError with the status code."""
    response = _response(status_code=400, text="invalid_grant")

    with pytest.raises(SpotifyAuthError, match="400"):
        parse_token_response(response)
