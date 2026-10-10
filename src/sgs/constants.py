"""Module for storing project constants."""

from pathlib import Path


# --- Relative file paths within repository ---


CONFIG_PATH = Path(__file__).parent / "configs" / "config.yaml"
CACHE_DB_PATH = Path("data") / "spotify_cache.db"


# --- Related to Spotify authentication and retrieving data ---


SPOTIFY_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"
SPOTIFY_ME_URL = f"{SPOTIFY_API_BASE_URL}/me"
SPOTIFY_ME_PLAYLISTS_URL = f"{SPOTIFY_API_BASE_URL}/me/playlists"
SPOTIFY_ME_TRACKS_URL = f"{SPOTIFY_API_BASE_URL}/me/tracks"
SPOTIFY_ME_ALBUMS_URL = f"{SPOTIFY_API_BASE_URL}/me/albums"
SPOTIFY_ME_TOP_TRACKS_URL = f"{SPOTIFY_API_BASE_URL}/me/top/tracks"
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

# Top tracks are re-read from Spotify after this many hours.
TOP_TRACKS_MAX_AGE_HOURS = 24


# --- Related to the caching database ---


PLAYLIST_SOURCE_NAME = "your_playlists"
LIKED_SOURCE_NAME = "liked_songs"
SAVED_ALBUMS_SOURCE_NAME = "saved_albums"
TOP_TRACKS_SOURCE_NAME = "top_tracks"
