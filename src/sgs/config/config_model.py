"""Module for Pydantic configuration models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConfiguredBaseModel(BaseModel):
    """Config that disallows extra parameters not explicitly defined"""

    model_config = ConfigDict(extra="forbid")


class ConfigModel(ConfiguredBaseModel):
    """Config that combines all parameters"""

    class Sources(ConfiguredBaseModel):
        """Which song sources to read from"""

        liked_songs: bool
        saved_albums: bool
        top_tracks: bool
        your_playlists: bool

    class Options(ConfiguredBaseModel):
        """Settings that change how the sources are read"""

        top_tracks_time_range: Literal["short_term", "medium_term", "long_term"]
        include_collaborative_playlists: bool

    sources: Sources
    options: Options
