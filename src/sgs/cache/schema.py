"""Table definitions for the Spotify cache database."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    song_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uri TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artists (
    artist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS genres (
    genre_name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS artist_genres (
    artist_id TEXT REFERENCES artists(artist_id),
    genre_name TEXT REFERENCES genres(genre_name),
    PRIMARY KEY (artist_id, genre_name)
);

CREATE TABLE IF NOT EXISTS song_artists (
    song_id TEXT REFERENCES songs(song_id),
    artist_id TEXT REFERENCES artists(artist_id),
    position INTEGER NOT NULL,
    PRIMARY KEY (song_id, artist_id)
);

CREATE TABLE IF NOT EXISTS playlists (
    playlist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    collaborative BOOLEAN NOT NULL,
    snapshot_id TEXT NOT NULL,
    synced_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id TEXT REFERENCES playlists(playlist_id),
    position INTEGER NOT NULL,
    song_id TEXT REFERENCES songs(song_id),
    PRIMARY KEY (playlist_id, position)
);

CREATE TABLE IF NOT EXISTS library_items (
    source_name TEXT NOT NULL,
    item_id TEXT NOT NULL,
    added_at TIMESTAMP NOT NULL,
    PRIMARY KEY (source_name, item_id)
);

CREATE TABLE IF NOT EXISTS album_songs (
    album_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    song_id TEXT REFERENCES songs(song_id),
    PRIMARY KEY (album_id, position)
);

CREATE TABLE IF NOT EXISTS top_track_rankings (
    time_range TEXT NOT NULL,
    position INTEGER NOT NULL,
    song_id TEXT REFERENCES songs(song_id),
    fetched_at TIMESTAMP NOT NULL,
    PRIMARY KEY (time_range, position)
);

CREATE TABLE IF NOT EXISTS artist_genre_responses (
    artist_id TEXT NOT NULL REFERENCES artists(artist_id),
    source TEXT NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (artist_id, source)
);

CREATE TABLE IF NOT EXISTS raw_tracks (
    song_id TEXT PRIMARY KEY,
    fetched_at TIMESTAMP NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_albums (
    album_id TEXT PRIMARY KEY,
    fetched_at TIMESTAMP NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_artists (
    artist_id TEXT PRIMARY KEY,
    fetched_at TIMESTAMP NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS song_sources (
    song_id TEXT REFERENCES songs(song_id),
    source_name TEXT NOT NULL,
    PRIMARY KEY (song_id, source_name)
);
"""


def create_schema(connection: sqlite3.Connection) -> None:
    """Creates every table that does not exist yet.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
    """

    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
