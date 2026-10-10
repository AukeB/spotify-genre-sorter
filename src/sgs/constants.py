"""Module for storing project constants."""

from pathlib import Path

# --- Relative file paths within repository.

CONFIG_PATH = Path(__file__).parent / "configs" / "config.yaml"
CACHE_DB_PATH = Path("data") / "spotify_cache.db"

# --- Related to Spotify authentication

SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"
SPOTIFY_ME_URL = f"{SPOTIFY_API_BASE_URL}/me"
SPOTIFY_ME_PLAYLISTS_URL = f"{SPOTIFY_API_BASE_URL}/me/playlists"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:5000/callback"
SPOTIFY_SCOPES = [
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-top-read",
]

# Seconds to wait for the browser to return the authorization code.
LOGIN_TIMEOUT_SECONDS = 120
# Refresh the access token this many seconds before it actually expires.
TOKEN_EXPIRY_MARGIN_SECONDS = 60
