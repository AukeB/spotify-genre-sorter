"""Module for running the main repository workflow."""

import logging

import typer

from sgs.authentication import SpotifyAuthenticator
from sgs.config.config_manager import ConfigManager
from sgs.song_sources import SongSources
from sgs.spotify_cache import SpotifyCache
from sgs.api.spotify_api import fetch_current_user

logger = logging.getLogger(__name__)

app = typer.Typer(help="Log in to Spotify and show the user.")


@app.command()
def main(
    spotify_client_id: str = typer.Option(
        ..., "--spotify-client-id", help="Spotify app client ID."
    ),
    lastfm_api_key: str | None = typer.Option(
        None,
        "--lastfm-api-key",
        help="Last.fm API key. Skips Last.fm when not given.",
    ),
) -> None:
    """
    Log in to Spotify, collect the songs, and cache the genre data.

    1. Read the Spotify client ID and the optional Last.fm key from the command line.
    2. Run the PKCE login in the browser and keep the token in memory.
    3. Call the current-user endpoint to confirm the token works.
    4. Collect the songs from the enabled sources.
    5. Request genre data from MusicBrainz, and from Last.fm when a key is given.
    """
    authenticator = SpotifyAuthenticator(client_id=spotify_client_id)
    access_token = authenticator.get_valid_token()
    user = fetch_current_user(access_token)
    
    logger.info("Logged in as: %s", user["display_name"])

    config = ConfigManager().load_config_file()
    songs = SongSources(config, access_token).get_all_songs()
    logger.info("Found %d unique songs", len(songs))

    with SpotifyCache() as cache:
        cache.sync_genre_responses(lastfm_api_key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(name)-20s: %(message)s")
    app()
