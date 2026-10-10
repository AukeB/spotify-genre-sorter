"""Reads songs from the sources enabled in config.yaml."""

import logging
import time
from collections.abc import Iterable

from sgs.config_model import ConfigModel
from sgs.constants import SPOTIFY_API_BASE_URL
from sgs.models import Song
from sgs.spotify_api import fetch_current_user, get_all_pages
from sgs.spotify_cache import PLAYLIST_SOURCE_NAME, SpotifyCache

logger = logging.getLogger(__name__)


def _to_songs(tracks: Iterable[dict | None], source: str) -> list[Song]:
    """Converts Spotify track objects into Song models.

    Args:
        tracks (Iterable[dict | None]): Track objects. Missing or unavailable
            tracks are skipped.
        source (str): The config source name to record on each song.

    Returns:
        songs (list[Song]): The songs that have a track ID.
    """
    songs = []

    for track in tracks:
        if track is None or track.get("id") is None:
            continue

        artist_ids = [artist["id"] for artist in track["artists"]]

        song = Song(
            id=track["id"],
            name=track["name"],
            uri=track["uri"],
            artist_ids=artist_ids,
            sources={source},
        )

        songs.append(song)

    return songs


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

    def __init__(self, config: ConfigModel, access_token: str) -> None:
        """Initializes the sources with the settings from the config.

        Args:
            config (ConfigModel): The loaded configuration.
            access_token (str): A valid Spotify access token.
        """
        self._access_token = access_token
        self._liked_songs_enabled = config.sources.liked_songs
        self._saved_albums_enabled = config.sources.saved_albums
        self._top_tracks_enabled = config.sources.top_tracks
        self._your_playlists_enabled = config.sources.your_playlists
        self._top_tracks_time_range = config.options.top_tracks_time_range
        self._include_collaborative_playlists = (
            config.options.include_collaborative_playlists
        )

    def _fetch_liked_songs(self) -> list[Song]:
        """Reads the tracks in the user's library.

        Returns:
            songs (list[Song]): The liked songs.
        """
        items = get_all_pages(f"{SPOTIFY_API_BASE_URL}/me/tracks", self._access_token)
        tracks = [item["track"] for item in items]
        songs = _to_songs(tracks, "liked_songs")

        return songs

    def _fetch_saved_albums(self) -> list[Song]:
        """Reads every track from the user's saved albums.

        Each album's track list is fetched separately, so albums longer than one
        page are read in full.

        Returns:
            songs (list[Song]): The tracks from all saved albums.
        """
        items = get_all_pages(f"{SPOTIFY_API_BASE_URL}/me/albums", self._access_token)
        albums = [item["album"] for item in items]

        logger.info("Found %d saved albums", len(albums))

        songs = []

        for album in albums:
            album_tracks = get_all_pages(
                f"{SPOTIFY_API_BASE_URL}/albums/{album['id']}/tracks",
                self._access_token,
            )
            album_songs = _to_songs(album_tracks, "saved_albums")
            logger.info("Album %s: %d tracks", album["name"], len(album_songs))
            songs.extend(album_songs)

        return songs

    def _fetch_top_tracks(self) -> list[Song]:
        """Reads the user's top tracks for the configured time range.

        Returns:
            songs (list[Song]): The top tracks.
        """
        items = get_all_pages(
            f"{SPOTIFY_API_BASE_URL}/me/top/tracks",
            self._access_token,
            params={"time_range": self._top_tracks_time_range},
        )

        songs = _to_songs(items, "top_tracks")

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

        start = time.perf_counter()

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

        elapsed = time.perf_counter() - start
        logger.info("Total song collection took %.2f s", elapsed)

        return all_songs
