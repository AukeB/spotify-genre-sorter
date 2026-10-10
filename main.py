"""Module for running the main repository workflow."""

import logging

import typer

from sgs.authentication import SpotifyAuthenticator
from sgs.spotify_api import fetch_current_user

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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    authenticator = SpotifyAuthenticator(client_id=client_id)
    access_token = authenticator.get_valid_token()
    user = fetch_current_user(access_token)
    
    print(f"Logged in as: {user['display_name']}")


if __name__ == "__main__":
    app()
