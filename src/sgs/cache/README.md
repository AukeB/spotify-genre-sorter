# Cache modules

This folder holds the parts of the Spotify cache. The app uses only `SpotifyCache` in `src/sgs/spotify_cache.py`, which calls into the modules here. The cache is a local SQLite file at `data/spotify_cache.db`. For the table layout and the reasons behind the cache, see [docs/spotify_cache.md](../../../docs/spotify_cache.md).

## How a sync works

Each source has a sync step that reads from Spotify and writes to the database. After a sync, `get_songs_for_source()` reads the songs back from the database without calling Spotify. Items that have not changed are skipped, so repeated runs are much faster.

## Modules

| Module | Purpose |
|---|---|
| `schema.py` | Defines every table and creates the missing ones when the cache opens. |
| `playlist_cache.py` | Syncs playlists. A playlist is read again only when its `snapshot_id` changes. Playlists that are no longer readable are removed. |
| `library_cache.py` | Syncs liked songs and saved albums. Reads only items added since the last run, and re-reads the whole list when the cached count differs from Spotify's total. Contains the shared base class `LibraryCache` and two subclasses, `LikedSongsCache` and `SavedAlbumsCache`. |
| `genre_response_cache.py` | Requests MusicBrainz and Last.fm for each artist that has no response from them yet. Stores the raw JSON, one row per artist and source. Parsing comes later. |
| `top_track_cache.py` | Syncs top tracks per time range. Re-reads a ranking only when it is older than `TOP_TRACKS_MAX_AGE_HOURS`. |
| `track_store.py` | Saves a track, its artists, and the links between them. Every source uses it, so a song is stored the same way wherever it was found. |
| `source_links.py` | Keeps the `song_sources` rows in line with the cached data, so each song records the sources it came from. |
| `song_reader.py` | Reads cached songs for one source back out of the database, with no Spotify calls. |
| `sync_stats.py` | Counts rows added and changed during a sync, and times the sync. Logs both when the sync ends. |
| `track_filters.py` | Drops null entries from Spotify track lists. |

## Order of work during a full sync

1. `playlist_cache.py` syncs playlists and their songs.
2. `library_cache.py` syncs liked songs, then saved albums.
3. `top_track_cache.py` syncs top tracks for the configured time range.
4. `genre_response_cache.py` requests MusicBrainz, and Last.fm when a key is given, for artists that have no response yet.

The first three steps write their songs through `track_store.py` and their links through `source_links.py`. Timestamps come from `src/sgs/utils/time_utils.py`.
