"""Module for testing authentication/callback_handler.py"""

import threading
import urllib.error
import urllib.request

from sgs.authentication.callback_handler import CallbackHandler, CallbackServer


def _serve_one_request(path):
    """Starts a loopback callback server, sends one GET request, and returns the server."""
    server = CallbackServer(("127.0.0.1", 0), CallbackHandler)
    server.callback_params = None
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    url = f"http://127.0.0.1:{server.server_address[1]}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    thread.join(timeout=5)
    server.server_close()
    return server, status


# Testing the "do_GET" method from the "CallbackHandler" class.


def test_callback_stores_query_parameters():
    """A request to the callback path stores its query parameters."""
    server, status = _serve_one_request("/callback?code=abc&state=xyz")

    assert status == 200
    assert server.callback_params == {"code": "abc", "state": "xyz"}


def test_callback_wrong_path_returns_404():
    """A request to any other path is rejected and stores nothing."""
    server, status = _serve_one_request("/other?code=abc")

    assert status == 404
    assert server.callback_params is None
