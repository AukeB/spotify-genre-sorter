"""Spotify login using Authorization Code with PKCE.

No client secret is needed, and tokens are kept in memory only. Each new process
performs one browser login.
"""

from sgs.authentication.authentication import SpotifyAuthenticator
from sgs.authentication.token_model import TokenInfo

__all__ = ["SpotifyAuthenticator", "TokenInfo"]
