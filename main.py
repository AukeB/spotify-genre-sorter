"""Module for running the main repository workflow."""

import logging

import typer

from sgs.api.spotify_api import fetch_current_user
from sgs.authentication import SpotifyAuthenticator
from sgs.cache.track_inspector import (
    build_track_report,
    open_read_only,
    parse_track_id,
)

from sgs.config.config_manager import ConfigManager
from sgs.constants import CACHE_DB_PATH
from sgs.song_sources import SongSources
from sgs.spotify_cache import SpotifyCache

logger = logging.getLogger(__name__)

app = typer.Typer(
    help="Group your Spotify songs into genre playlists, and inspect the cache.",
)


@app.command("run")
def run(
    spotify_client_id: str = typer.Option(
        ..., "--spotify-client-id", help="Spotify app client ID."
    ),
    lastfm_api_key: str | None = typer.Option(
        None,
        "--lastfm-api-key",
        help="Last.fm API key. Skips Last.fm when not given.",
    ),
    refresh_spotify: bool = typer.Option(
        False,
        "--refresh-spotify",
        help=(
            "Read the Spotify data again, including items already cached, so that "
            "raw copies are stored for them. Does not call MusicBrainz or Last.fm."
        ),
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
    songs = SongSources(config, access_token, refresh_spotify).get_all_songs()
    logger.info("Found %d unique songs", len(songs))

    with SpotifyCache() as cache:
        cache.sync_genre_responses(lastfm_api_key)


@app.command("track")
def track(
    track_id: str | None = typer.Option(
        None, "--track-id", help="Spotify track ID, such as 4F2QVxqYaLlsZQx70Wngct."
    ),
    track_link: str | None = typer.Option(
        None,
        "--track-link",
        help="Spotify track link or URI, such as https://open.spotify.com/track/....",
    ),
    raw: bool = typer.Option(
        False, "--raw", help="Print the full stored JSON instead of a summary."
    ),
) -> None:
    """
    Show everything the cache stores about one track.

    Give either --track-id or --track-link. The report is read-only and does not
    call Spotify.
    """
    try:
        spotify_id = parse_track_id(track_id, track_link)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    try:
        connection = open_read_only(CACHE_DB_PATH)
    except FileNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    try:
        report = build_track_report(connection, spotify_id, include_raw=raw)
    finally:
        connection.close()

    typer.echo(report)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(name)-20s: %(message)s")
    app()
