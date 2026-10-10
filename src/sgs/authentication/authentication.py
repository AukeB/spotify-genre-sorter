"""Handles the Spotify PKCE login and keeps the token in memory."""

import logging
import webbrowser
from urllib.parse import urlencode, urlparse

import requests

from sgs.authentication.callback_handler import CallbackHandler, CallbackServer
from sgs.authentication.token_model import TokenInfo
from sgs.authentication.utils import (
    generate_pkce_pair,
    generate_state,
    parse_token_response,
)
from sgs.constants import (
    LOGIN_TIMEOUT_SECONDS,
    SPOTIFY_AUTHORIZE_URL,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPES,
    SPOTIFY_TOKEN_URL,
)
from sgs.errors import SpotifyAuthError

logger = logging.getLogger(__name__)


class SpotifyAuthenticator:
    """Handles the Spotify PKCE login and keeps the token in memory.

    Attributes:
        client_id (str): The Spotify app client ID.
        redirect_uri (str): The redirect URI registered in the Spotify app.
        scopes (list[str]): Scopes requested during login.

    Example:
        >>> authenticator = SpotifyAuthenticator(client_id="your-client-id")
        >>> access_token = authenticator.get_valid_token()
    """

    def __init__(
        self,
        client_id: str,
        redirect_uri: str = SPOTIFY_REDIRECT_URI,
        scopes: list[str] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Initializes the authenticator.

        Args:
            client_id (str): The Spotify app client ID.
            redirect_uri (str): The redirect URI registered in the Spotify app.
            scopes (list[str] | None): Scopes to request. Defaults to
                SPOTIFY_SCOPES.
            session (requests.Session | None): HTTP session, injectable for
                tests.
        """
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scopes = scopes if scopes is not None else SPOTIFY_SCOPES
        self._session = session or requests.Session()
        self._token: TokenInfo | None = None

    def _build_authorize_url(self, state: str, code_challenge: str) -> str:
        """Builds the URL the user opens to approve access.

        Args:
            state (str): Random state value checked on the callback.
            code_challenge (str): PKCE code challenge.

        Returns:
            authorize_url (str): The full authorization URL.
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }

        authorize_url = f"{SPOTIFY_AUTHORIZE_URL}?{urlencode(params)}"

        return authorize_url

    def _wait_for_auth_code(self, state: str) -> str:
        """Runs a local server and waits for Spotify to redirect with a code.

        Args:
            state (str): The state value sent in the authorization request.

        Returns:
            code (str): The authorization code.

        Raises:
            SpotifyAuthError: If the server cannot start, the state does not
                match, the user denied access, or no callback arrives in time.
        """
        parsed = urlparse(self.redirect_uri)

        if parsed.hostname is None or parsed.port is None:
            raise SpotifyAuthError(
                f"Redirect URI needs a host and port: {self.redirect_uri}"
            )

        try:
            server = CallbackServer((parsed.hostname, parsed.port), CallbackHandler)
        except OSError as error:
            raise SpotifyAuthError(
                f"Could not start callback server on {self.redirect_uri}: {error}"
            ) from error

        server.timeout = LOGIN_TIMEOUT_SECONDS

        try:
            server.handle_request()
        finally:
            server.server_close()

        params = server.callback_params

        if params is None:
            raise SpotifyAuthError("Timed out waiting for the Spotify callback.")
        if params.get("state") != state:
            raise SpotifyAuthError("State mismatch in Spotify callback.")
        if "error" in params:
            raise SpotifyAuthError(f"Spotify login failed: {params['error']}")
        if "code" not in params:
            raise SpotifyAuthError("Spotify callback did not include a code.")

        code = params["code"]

        return code

    def _exchange_code(self, code: str, code_verifier: str) -> TokenInfo:
        """Exchanges an authorization code for an access token.

        Args:
            code (str): The authorization code from the callback.
            code_verifier (str): The PKCE code verifier used to start the login.

        Returns:
            token (TokenInfo): The new token.
        """
        response = self._session.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )

        token = parse_token_response(response)

        return token

    def _refresh(self, refresh_token: str) -> TokenInfo:
        """Gets a new access token using a refresh token.

        Args:
            refresh_token (str): The refresh token from an earlier token
                response.

        Returns:
            token (TokenInfo): The refreshed token.
        """
        response = self._session.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )

        token = parse_token_response(response, previous_refresh_token=refresh_token)

        return token

    def login(self) -> TokenInfo:
        """Runs the full browser login and stores the resulting token in memory.

        Returns:
            token (TokenInfo): The new token.
        """
        code_verifier, code_challenge = generate_pkce_pair()
        state = generate_state()
        authorize_url = self._build_authorize_url(state, code_challenge)

        logger.info(
            "Opening browser for Spotify login. If it does not open, visit: %s",
            authorize_url,
        )
        webbrowser.open(authorize_url)

        code = self._wait_for_auth_code(state)
        self._token = self._exchange_code(code, code_verifier)

        return self._token

    def get_valid_token(self) -> str:
        """Returns a usable access token, refreshing or logging in when needed.

        Returns:
            access_token (str): A valid access token.
        """
        if self._token is None:
            access_token = self.login().access_token

            return access_token

        if self._token.is_expired():
            if self._token.refresh_token is None:
                access_token = self.login().access_token

                return access_token
            try:
                self._token = self._refresh(self._token.refresh_token)
            except SpotifyAuthError:
                access_token = self.login().access_token

                return access_token

        access_token = self._token.access_token

        return access_token
