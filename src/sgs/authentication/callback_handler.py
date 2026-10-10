"""Local HTTP server that receives Spotify's login redirect.

During the browser login, Spotify sends the user back to the redirect URI
(http://127.0.0.1:5000/callback in this project) with either an authorization
code or an error. Nothing else is listening on that address, so the app starts a
short-lived server there to catch that single request.

CallbackServer holds the query parameters of the request. CallbackHandler is the
request handler that reads them, responds with a "Login complete" page, and
stores the parameters on the server for SpotifyAuthenticator to read.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast
from urllib.parse import parse_qs, urlparse

from sgs.constants import SPOTIFY_REDIRECT_URI


class CallbackServer(HTTPServer):
    """Local HTTP server that holds the query parameters of the login callback."""

    callback_params: dict[str, str] | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Handles the single redirect from Spotify and stores its query parameters."""

    def do_GET(self) -> None:  # noqa: N802 (name required by BaseHTTPRequestHandler)
        """Stores the query parameters of the callback and shows a message."""
        parsed = urlparse(self.path)
        if parsed.path != urlparse(SPOTIFY_REDIRECT_URI).path:
            self.send_error(404)

            return

        server = cast(CallbackServer, self.server)
        server.callback_params = {
            key: values[0] for key, values in parse_qs(parsed.query).items()
        }

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><p>Login complete. You can close this tab.</p></body></html>"
        )

    def log_message(self, format: str, *args) -> None:
        """Silences the default request logging."""
        return
