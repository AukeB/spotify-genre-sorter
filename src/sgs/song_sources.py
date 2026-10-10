"""Reads songs from the sources enabled in config.yaml."""

import logging
import time

from sgs.config.config_model import ConfigModel
from sgs.constants import (
    LIKED_SOURCE_NAME,
    PLAYLIST_SOURCE_NAME,
    SAVED_ALBUMS_SOURCE_NAME,
    TOP_TRACKS_SOURCE_NAME,
)

from sgs.models import Song
from sgs.api.spotify_api import fetch_current_user
from sgs.spotify_cache import SpotifyCache

logger = logging.getLogger(__name__)


class SongSources:
    """Reads songs from the sources enabled in the config and merges them.

    Attributes:
        _access_token (str): Access token used for every Spotify request.
        _liked_songs_enabled (bool): Whether to read liked songs.
        _saved_albums_enabled (bool): Whether to read tracks from saved albums.
        _top_tracks_enabled (bool): Whether to read the user's top tracks.
        _your_playlists_enabled (bool): Whether to read tracks from the user's
            playlists.
        _top_tracks_time_range (str): Period used for top tracks.
        _include_collaborative_playlists (bool): Whether to read collaborative
            playlists owned by other users.

    Example:
        >>> songs = SongSources(config, access_token).get_all_songs()
    """

    def __init__(
        self, config: ConfigModel, access_token: str, refresh_spotify: bool = False
    ) -> None:
        """Initializes the sources with the settings from the config.

        Args:
            config (ConfigModel): The loaded configuration.
            access_token (str): A valid Spotify access token.
            refresh_spotify (bool): If True, read every Spotify source again,
                including items already cached.
        """
        self._access_token = access_token
        self._refresh_spotify = refresh_spotify
        self._liked_songs_enabled = config.sources.liked_songs
        self._saved_albums_enabled = config.sources.saved_albums
        self._top_tracks_enabled = config.sources.top_tracks
        self._your_playlists_enabled = config.sources.your_playlists
        self._top_tracks_time_range = config.options.top_tracks_time_range
        self._include_collaborative_playlists = (
            config.options.include_collaborative_playlists
        )

    def _fetch_liked_songs(self) -> list[Song]:
        """Reads the tracks in the user's library through the local cache.

        Only tracks added since the last run are read from Spotify.

        Returns:
            songs (list[Song]): The liked songs.
        """
        with SpotifyCache() as cache:
            cache.sync_liked_songs(self._access_token, self._refresh_spotify)

            songs = cache.get_songs_for_source(LIKED_SOURCE_NAME)

        return songs

    def _fetch_saved_albums(self) -> list[Song]:
        """Reads every track from the user's saved albums through the local
        cache.

        Only albums added since the last run have their tracks read from
        Spotify.

        Returns:
            songs (list[Song]): The tracks from all saved albums.
        """
        with SpotifyCache() as cache:
            cache.sync_saved_albums(self._access_token, self._refresh_spotify)

            songs = cache.get_songs_for_source(SAVED_ALBUMS_SOURCE_NAME)

        return songs

    def _fetch_top_tracks(self) -> list[Song]:
        """Reads the user's top tracks through the local cache.

        The ranking is read from Spotify again only when the cached one is older
        than TOP_TRACKS_MAX_AGE_HOURS.

        Returns:
            songs (list[Song]): The top tracks.
        """
        with SpotifyCache() as cache:
            cache.sync_top_tracks(
                self._access_token,
                self._top_tracks_time_range,
                self._refresh_spotify,
            )

            songs = cache.get_songs_for_source(TOP_TRACKS_SOURCE_NAME)

        return songs

    def _fetch_your_playlists(self) -> list[Song]:
        """Reads the tracks from the user's playlists through the local cache.

        The cache re-reads only playlists that changed since the last run. Only
        playlists the user owns are read, plus collaborative playlists when
        `include_collaborative_playlists` is enabled.

        Returns:
            songs (list[Song]): The tracks from the readable playlists.
        """
        user_id = fetch_current_user(self._access_token)["id"]

        with SpotifyCache() as cache:
            cache.sync_playlists(
                self._access_token,
                user_id,
                self._include_collaborative_playlists,
                self._refresh_spotify,
            )

            songs = cache.get_songs_for_source(PLAYLIST_SOURCE_NAME)

        return songs

    def get_all_songs(self) -> list[Song]:
        """Reads every enabled source and merges the results by track ID.

        A track found in several sources appears once, with all of those sources
        listed. Different releases of a song have different track IDs, so they
        remain separate songs.

        Returns:
            all_songs (list[Song]): The unique songs from all enabled sources.
        """
        enabled_fetchers = [
            (self._liked_songs_enabled, self._fetch_liked_songs),
            (self._saved_albums_enabled, self._fetch_saved_albums),
            (self._top_tracks_enabled, self._fetch_top_tracks),
            (self._your_playlists_enabled, self._fetch_your_playlists),
        ]

        songs_by_id: dict[str, Song] = {}

        total_start = time.perf_counter()

        for enabled, fetch in enabled_fetchers:
            if not enabled:
                continue

            start = time.perf_counter()
            songs = fetch()
            elapsed = time.perf_counter() - start
            logger.info(
                "Read %d songs from %s in %.2f s",
                len(songs),
                fetch.__name__,
                elapsed,
            )

            for song in songs:
                existing = songs_by_id.get(song.id)

                if existing is None:
                    songs_by_id[song.id] = song
                else:
                    existing.sources |= song.sources

        all_songs = list(songs_by_id.values())

        total_elapsed = time.perf_counter() - total_start
        logger.info("Total song collection took %.2f s", total_elapsed)

        return all_songs
