"""Reads songs from the sources enabled in config.yaml."""

import logging
from collections.abc import Iterable

from sgs.config_model import ConfigModel
from sgs.constants import SPOTIFY_API_BASE_URL
from sgs.models import Song
from sgs.spotify_api import fetch_current_user, get_all_pages

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

    def _is_readable_playlist(self, playlist: dict, user_id: str) -> bool:
        """Checks whether the playlist's items can be read.

        A playlist is readable when either of these is true:
        1. The logged-in user owns it.
        2. It is collaborative and `include_collaborative_playlists` is enabled.

        Playlists the user only follows are not readable, because Spotify
        returns 403 for their items.

        Args:
            playlist (dict): A playlist object from the current-user playlists
                endpoint.
            user_id (str): The ID of the logged-in user.

        Returns:
            readable (bool): True if the playlist meets one of the conditions
                above.
        """
        is_owner = playlist["owner"]["id"] == user_id
        is_collaborative = (
            playlist["collaborative"] and self._include_collaborative_playlists
        )
        readable = is_owner or is_collaborative

        return readable

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

        songs = []

        for album in albums:
            album_tracks = get_all_pages(
                f"{SPOTIFY_API_BASE_URL}/albums/{album['id']}/tracks",
                self._access_token,
            )
            album_songs = _to_songs(album_tracks, "saved_albums")
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
        """Reads the tracks from the user's playlists.

        Only playlists the user owns are read, plus collaborative playlists when
        `include_collaborative_playlists` is enabled. Spotify does not allow
        reading the other playlists the user follows.

        Returns:
            songs (list[Song]): The tracks from the readable playlists.
        """
        user_id = fetch_current_user(self._access_token)["id"]
        playlists = get_all_pages(
            f"{SPOTIFY_API_BASE_URL}/me/playlists", self._access_token
        )

        songs = []

        for playlist in playlists:
            if not self._is_readable_playlist(playlist, user_id):
                continue

            entries = get_all_pages(
                f"{SPOTIFY_API_BASE_URL}/playlists/{playlist['id']}/items",
                self._access_token,
            )
            tracks = []

            for entry in entries:
                item = entry.get("item")
                if item is None or entry.get("is_local") or item.get("type") != "track":
                    continue

                tracks.append(item)

            playlist_songs = _to_songs(tracks, "your_playlists")
            songs.extend(playlist_songs)

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

        for enabled, fetch in enabled_fetchers:
            if not enabled:
                continue

            songs = fetch()
            logger.info("Read %d songs from %s", len(songs), fetch.__name__)

            for song in songs:
                existing = songs_by_id.get(song.id)

                if existing is None:
                    songs_by_id[song.id] = song
                else:
                    existing.sources |= song.sources

        all_songs = list(songs_by_id.values())

        return all_songs
