"""Module for running the main repository workflow."""

import logging

import typer

from sgs.authentication import SpotifyAuthenticator
from sgs.config_manager import ConfigManager
from sgs.song_sources import SongSources
from sgs.spotify_cache import SpotifyCache
from sgs.spotify_api import fetch_current_user

logger = logging.getLogger(__name__)

app = typer.Typer(help="Log in to Spotify and show the user.")


@app.command()
def main(
    client_id: str = typer.Option(..., "--client-id", help="Spotify app client ID."),
) -> None:
    """
    Log in to Spotify and print the name of the logged-in user.

    1. Read the Spotify client ID from the command line.
    2. Run the PKCE login in the browser and keep the token in memory.
    3. Call the current-user endpoint to confirm the token works.
    """
    authenticator = SpotifyAuthenticator(client_id=client_id)
    access_token = authenticator.get_valid_token()
    user = fetch_current_user(access_token)
    
    logger.info("Logged in as: %s", user["display_name"])

    config = ConfigManager().load_config_file()
    songs = SongSources(config, access_token).get_all_songs()
    logger.info("Found %d unique songs", len(songs))

    with SpotifyCache() as cache:
        cache.sync_artist_genres(access_token)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(name)-20s: %(message)s")
    app()
