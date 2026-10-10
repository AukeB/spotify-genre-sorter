"""Local SQLite cache of the Spotify data the genre sorter needs.

SpotifyCache is the only class the rest of the app uses. The work is split
across the modules in sgs.cache.
"""

import sqlite3
from pathlib import Path

from sgs.cache.artist_genre_cache import ArtistGenreCache
from sgs.cache.library_cache import LikedSongsCache, SavedAlbumsCache
from sgs.cache.playlist_cache import PlaylistCache
from sgs.cache.schema import create_schema
from sgs.cache.song_reader import read_songs_for_source
from sgs.cache.source_links import SourceLinks
from sgs.cache.sync_stats import SyncStats
from sgs.cache.top_track_cache import TopTrackCache
from sgs.cache.track_store import TrackStore
from sgs.constants import CACHE_DB_PATH
from sgs.models import Song


class SpotifyCache:
    """Local cache of songs, artists, playlists, albums, and top tracks.

    The cache is a subset of the Spotify data, kept in SQLite so that repeated
    runs do not call the API again for data that has not changed.

    Each source has its own sync method. Sync must run before reading, otherwise
    the cache may be empty or stale:

    1. sync_playlists() keeps the readable playlists. A playlist is re-read only
       when its snapshot_id changes.
    2. sync_liked_songs() and sync_saved_albums() read only the items added
       since the last run. They stop at the first item already cached. If the
       total on Spotify no longer matches the cache, all items are read again so
       removals are noticed. A saved album's tracks are fetched once, when the
       album is first seen.
    3. sync_top_tracks() re-reads the ranking only when it is older than
       TOP_TRACKS_MAX_AGE_HOURS, because a ranking has no change marker.
    4. get_songs_for_source() reads the cached songs for one source from the
       database. It makes no API calls, so it can run as often as needed.

    Attributes:
        _connection (sqlite3.Connection): Open connection to the cache file.
        _stats (SyncStats): Counts and timing for the current sync.
        _playlists (PlaylistCache): Playlist sync.
        _liked_songs (LikedSongsCache): Liked songs sync.
        _saved_albums (SavedAlbumsCache): Saved albums sync.
        _top_tracks (TopTrackCache): Top tracks sync.
        _artist_genres (ArtistGenreCache): Artist genre sync.

    Example:
        >>> with SpotifyCache() as cache:
        ...     cache.sync_playlists(access_token, user_id, include_collaborative=True)
        ...     songs = cache.get_songs_for_source("your_playlists")
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Opens the cache file and creates any tables that are missing.

        Args:
            db_path (Path | None): Location of the cache file. Defaults to
                CACHE_DB_PATH when not given.
        """
        path = db_path or CACHE_DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = sqlite3.connect(path)
        create_schema(self._connection)

        self._stats = SyncStats()
        track_store = TrackStore(self._connection, self._stats)
        source_links = SourceLinks(self._connection, self._stats)

        self._playlists = PlaylistCache(
            self._connection, self._stats, track_store, source_links
        )
        self._liked_songs = LikedSongsCache(
            self._connection, self._stats, track_store, source_links
        )
        self._saved_albums = SavedAlbumsCache(
            self._connection, self._stats, track_store, source_links
        )
        self._top_tracks = TopTrackCache(
            self._connection, self._stats, track_store, source_links
        )
        self._artist_genres = ArtistGenreCache(self._connection, self._stats)

    def sync_playlists(
        self, access_token: str, user_id: str, include_collaborative: bool
    ) -> None:
        """Brings the cached playlists up to date with the Spotify account.

        Args:
            access_token (str): A valid Spotify access token.
            user_id (str): The ID of the logged-in user.
            include_collaborative (bool): Whether collaborative playlists owned
                by other users should be read.
        """
        start = self._stats.start_sync()
        self._playlists.sync(access_token, user_id, include_collaborative)
        self._stats.finish_sync("Playlist", start)

    def sync_liked_songs(self, access_token: str) -> None:
        """Brings the cached liked songs up to date with the Spotify account.

        Args:
            access_token (str): A valid Spotify access token.
        """
        start = self._stats.start_sync()
        self._liked_songs.sync(access_token)
        self._stats.finish_sync("Liked songs", start)

    def sync_saved_albums(self, access_token: str) -> None:
        """Brings the cached saved albums up to date with the Spotify account.

        Args:
            access_token (str): A valid Spotify access token.
        """
        start = self._stats.start_sync()
        self._saved_albums.sync(access_token)
        self._stats.finish_sync("Saved albums", start)

    def sync_top_tracks(self, access_token: str, time_range: str) -> None:
        """Brings the cached top tracks for a time range up to date.

        Args:
            access_token (str): A valid Spotify access token.
            time_range (str): The Spotify time range, such as "medium_term".
        """
        start = self._stats.start_sync()
        self._top_tracks.sync(access_token, time_range)
        self._stats.finish_sync("Top tracks", start)

    def sync_artist_genres(self, access_token: str) -> None:
        """Fetches the genres of every cached artist that does not have them
        yet.

        Call this after the source syncs, since it looks at the artists they
        stored.

        Args:
            access_token (str): A valid Spotify access token.
        """
        start = self._stats.start_sync()
        self._artist_genres.sync(access_token)
        self._stats.finish_sync("Artist genres", start)

    def get_songs_for_source(self, source_name: str) -> list[Song]:
        """Reads the cached songs that were found in a source.

        Args:
            source_name (str): The source to read, such as "your_playlists".

        Returns:
            songs (list[Song]): The songs from that source, with their artist
                IDs in credit order.
        """
        songs = read_songs_for_source(self._connection, source_name)

        return songs

    def close(self) -> None:
        """Closes the connection to the cache file."""
        self._connection.close()

    def __enter__(self) -> "SpotifyCache":
        """Returns the cache so it can be used in a with block.

        Returns:
            cache (SpotifyCache): This cache instance.
        """
        cache = self

        return cache

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Closes the connection when the with block ends.

        Python always calls this with three arguments, so they must be in the
        signature even though the method does not use them. When the block
        finished normally, all three are None. When it raised an error, they
        describe that error: its type, its value, and its traceback.

        The method returns None, which is falsy, so Python does not suppress an
        error raised inside the block. It is re-raised after the connection is
        closed.

        Args:
            exc_type (type[BaseException] | None): The class of the error raised
                inside the with block, or None if there was none.
            exc_value (BaseException | None): The error raised inside the with
                block, or None if there was none.
            traceback (TracebackType | None): The traceback of that error, or
                None if there was none.
        """
        self.close()
