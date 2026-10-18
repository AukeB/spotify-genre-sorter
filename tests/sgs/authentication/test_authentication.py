"""Module for testing authentication/authentication.py"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from sgs.authentication import SpotifyAuthenticator, TokenInfo
from sgs.constants import SPOTIFY_AUTHORIZE_URL, SPOTIFY_REDIRECT_URI, SPOTIFY_SCOPES
from sgs.errors import SpotifyAuthError

MODULE = "sgs.authentication.authentication"


def _token(expires_in: int = 3600, refresh_token: str | None = "refresh-1"):
    """Builds a TokenInfo that expires after the given number of seconds.

    Args:
        expires_in (int): Seconds until the token expires.
        refresh_token (str | None): The refresh token to store, or None.
    """

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    token = TokenInfo(
        access_token="access-1",
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    return token


def _token_response(status_code=200, payload=None):
    """Builds a fake token endpoint response.

    Args:
        status_code (int): The HTTP status code.
        payload (dict): The JSON body of the response.
    """

    response = MagicMock()
    response.status_code = status_code
    response.text = ""

    response.json.return_value = payload or {
        "access_token": "access-2",
        "refresh_token": "refresh-2",
        "expires_in": 3600,
    }

    return response


@pytest.fixture(name="session")
def fixture_session():
    """A mocked requests session for the token endpoint."""
    session = MagicMock()
    session.post.return_value = _token_response()

    return session


@pytest.fixture(name="authenticator")
def fixture_authenticator(session):
    """An authenticator that uses the mocked session."""
    authenticator = SpotifyAuthenticator(client_id="client-id", session=session)

    return authenticator


# Testing the "_build_authorize_url" method from the "SpotifyAuthenticator" class.


def test_authorize_url_contains_pkce_parameters(authenticator):
    """The authorization URL carries the client ID, scopes, state, and PKCE challenge."""
    url = authenticator._build_authorize_url("state-1", "challenge-1")

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == SPOTIFY_AUTHORIZE_URL
    assert params["client_id"] == ["client-id"]
    assert params["redirect_uri"] == [SPOTIFY_REDIRECT_URI]
    assert params["scope"] == [" ".join(SPOTIFY_SCOPES)]
    assert params["state"] == ["state-1"]
    assert params["code_challenge"] == ["challenge-1"]
    assert params["code_challenge_method"] == ["S256"]


# Testing the "_exchange_code" method from the "SpotifyAuthenticator" class.


def test_exchange_code_posts_authorization_code(authenticator, session):
    """Exchanging a code sends the code and verifier and returns the new token."""
    token = authenticator._exchange_code("code-1", "verifier-1")

    data = session.post.call_args.kwargs["data"]
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "code-1"
    assert data["code_verifier"] == "verifier-1"
    assert token.access_token == "access-2"


# Testing the "_refresh" method from the "SpotifyAuthenticator" class.


def test_refresh_keeps_refresh_token_when_not_returned(authenticator, session):
    """A refresh without a new refresh token keeps the old one."""

    payload = {"access_token": "access-3", "expires_in": 3600}
    response = _token_response(payload=payload)
    session.post.return_value = response

    token = authenticator._refresh("refresh-1")

    assert token.access_token == "access-3"
    assert token.refresh_token == "refresh-1"


# Testing the "login" method from the "SpotifyAuthenticator" class.


def test_login_stores_token_from_callback(authenticator):
    """A full login opens the browser, waits for the code, and stores the token."""

    exchanged = _token()

    with (
        patch(f"{MODULE}.webbrowser.open") as mock_open,
        patch.object(authenticator, "_wait_for_auth_code", return_value="code-1"),
        patch.object(
            authenticator, "_exchange_code", return_value=exchanged
        ) as mock_exchange,
    ):
        token = authenticator.login()

    mock_open.assert_called_once()
    assert mock_exchange.call_args.args[0] == "code-1"
    assert authenticator._token is token


# Testing the "get_valid_token" method from the "SpotifyAuthenticator" class.


def test_get_valid_token_logs_in_when_no_token(authenticator):
    """Without a stored token, get_valid_token runs a login."""

    login_token = _token()

    with patch.object(authenticator, "login", return_value=login_token) as mock_login:
        access_token = authenticator.get_valid_token()

    mock_login.assert_called_once()
    assert access_token == "access-1"


def test_get_valid_token_reuses_valid_token(authenticator):
    """A valid stored token is returned without any network call."""
    authenticator._token = _token(expires_in=3600)

    with (
        patch.object(authenticator, "login") as mock_login,
        patch.object(authenticator, "_refresh") as mock_refresh,
    ):
        access_token = authenticator.get_valid_token()

    mock_login.assert_not_called()
    mock_refresh.assert_not_called()
    assert access_token == "access-1"


def test_get_valid_token_refreshes_expired_token(authenticator):
    """An expired token with a refresh token is refreshed."""
    authenticator._token = _token(expires_in=-10)
    refreshed = _token()
    refreshed.access_token = "access-refreshed"

    with patch.object(
        authenticator, "_refresh", return_value=refreshed
    ) as mock_refresh:
        access_token = authenticator.get_valid_token()

    mock_refresh.assert_called_once_with("refresh-1")
    assert access_token == "access-refreshed"


def test_get_valid_token_logs_in_when_refresh_fails(authenticator):
    """If refreshing fails, the user is sent through a new login."""
    authenticator._token = _token(expires_in=-10)

    refresh_error = SpotifyAuthError("nope")
    login_token = _token()

    with (
        patch.object(authenticator, "_refresh", side_effect=refresh_error),
        patch.object(authenticator, "login", return_value=login_token) as mock_login,
    ):
        access_token = authenticator.get_valid_token()

    mock_login.assert_called_once()
    assert access_token == "access-1"


def test_get_valid_token_logs_in_when_expired_without_refresh_token(authenticator):
    """An expired token with no refresh token leads to a new login."""
    authenticator._token = _token(expires_in=-10, refresh_token=None)
    login_token = _token()

    with patch.object(authenticator, "login", return_value=login_token) as mock_login:
        authenticator.get_valid_token()

    mock_login.assert_called_once()


def _fake_callback_server(callback_params):
    """Returns a stand-in for CallbackServer that reports the given parameters.

    Args:
        callback_params (dict[str, str] | None): The query parameters the server reports.
    """

    class FakeServer:
        """Fake server that skips the network and reports fixed callback params.

        Attributes:
            address (tuple[str, int]): The address the server was asked to bind.
            handler (type): The request handler class.
            callback_params (dict[str, str] | None): The parameters reported.
            timeout (float | None): Unused timeout value.
        """

        def __init__(self, address, handler):
            self.address = address
            self.handler = handler
            self.callback_params = callback_params
            self.timeout = None

        def handle_request(self):
            """Pretends to receive one request."""

        def server_close(self):
            """Pretends to close the server."""

    return FakeServer


# Testing the "_wait_for_auth_code" method from the "SpotifyAuthenticator" class.


def test_wait_for_auth_code_returns_code(authenticator):
    """A callback with the matching state returns the authorization code."""
    fake = _fake_callback_server({"code": "code-1", "state": "state-1"})

    with patch(f"{MODULE}.CallbackServer", fake):
        code = authenticator._wait_for_auth_code("state-1")

    assert code == "code-1"


@pytest.mark.parametrize(
    "params, message",
    [
        (None, "Timed out"),
        ({"code": "c", "state": "other"}, "State mismatch"),
        ({"error": "access_denied", "state": "s"}, "access_denied"),
        ({"state": "s"}, "did not include a code"),
    ],
)
def test_wait_for_auth_code_raises_on_bad_callback(authenticator, params, message):
    """Timeouts, state mismatches, denied access, and missing codes raise SpotifyAuthError."""
    fake = _fake_callback_server(params)

    with (
        patch(f"{MODULE}.CallbackServer", fake),
        pytest.raises(SpotifyAuthError, match=message),
    ):
        authenticator._wait_for_auth_code("s")


def test_wait_for_auth_code_raises_when_redirect_uri_has_no_port(session):
    """A redirect URI without a port cannot host the callback server."""

    authenticator = SpotifyAuthenticator(
        client_id="client-id",
        redirect_uri="http://127.0.0.1/callback",
        session=session,
    )

    with pytest.raises(SpotifyAuthError, match="needs a host and port"):
        authenticator._wait_for_auth_code("s")


def test_wait_for_auth_code_raises_when_server_cannot_start(authenticator):
    """If the callback server cannot bind its port, SpotifyAuthError is raised."""

    startup_error = OSError("address in use")

    with (
        patch(f"{MODULE}.CallbackServer", side_effect=startup_error),
        pytest.raises(SpotifyAuthError, match="Could not start callback server"),
    ):
        authenticator._wait_for_auth_code("s")
