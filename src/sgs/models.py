"""Pydantic models for the Spotify data used across the app."""

from pydantic import BaseModel


class Song(BaseModel):
    """A track read from Spotify, with the sources it was found in.

    Attributes:
        id (str): The Spotify track ID. Different releases of a song have
            different IDs.
        name (str): The track title.
        uri (str): The Spotify URI of the track.
        artist_ids (list[str]): IDs of the artists credited on the track.
        sources (set[str]): Names of the config sources the track was read from.
    """

    id: str
    name: str
    uri: str
    artist_ids: list[str]
    sources: set[str]
