"""Module for Pydantic configuration models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConfiguredBaseModel(BaseModel):
    """Config that disallows extra parameters not explicitly defined"""

    model_config = ConfigDict(extra="forbid")


class ConfigModel(ConfiguredBaseModel):
    """Config that combines all parameters

    Attributes:
        sources (ConfigModel.Sources): Which song sources to read from.
        options (ConfigModel.Options): Settings that change how the sources are
            read.
    """

    class Sources(ConfiguredBaseModel):
        """Which song sources to read from

        Attributes:
            liked_songs (bool): Read the saved tracks.
            saved_albums (bool): Read the saved albums.
            top_tracks (bool): Read the top tracks.
            your_playlists (bool): Read the user's playlists.
        """

        liked_songs: bool
        saved_albums: bool
        top_tracks: bool
        your_playlists: bool

    class Options(ConfiguredBaseModel):
        """Settings that change how the sources are read

        Attributes:
            top_tracks_time_range (str): The time range for the top tracks.
            include_collaborative_playlists (bool): Whether to read
                collaborative playlists.
        """

        top_tracks_time_range: Literal["short_term", "medium_term", "long_term"]
        include_collaborative_playlists: bool

    sources: Sources
    options: Options
