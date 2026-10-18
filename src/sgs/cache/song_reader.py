"""Reads songs back out of the cache."""

import sqlite3

from sgs.models import Song


def read_songs_for_source(
    connection: sqlite3.Connection, source_name: str
) -> list[Song]:
    """Reads the cached songs that were found in a source.

    Makes no Spotify calls. The songs come from the local database only.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        source_name (str): The source to read, such as "your_playlists".

    Returns:
        songs (list[Song]): The songs from that source, with their artist IDs in
            credit order.
    """

    song_rows = connection.execute(
        "SELECT songs.song_id, songs.name, songs.uri FROM songs "
        "JOIN song_sources ON song_sources.song_id = songs.song_id "
        "WHERE song_sources.source_name = ?",
        (source_name,),
    ).fetchall()

    artist_rows = connection.execute(
        "SELECT song_id, artist_id FROM song_artists ORDER BY song_id, position"
    ).fetchall()

    artist_ids_by_song: dict[str, list[str]] = {}

    for song_id, artist_id in artist_rows:
        artist_ids = artist_ids_by_song.setdefault(song_id, [])
        artist_ids.append(artist_id)

    songs = []

    for song_id, name, uri in song_rows:
        artist_ids = artist_ids_by_song.get(song_id, [])

        song = Song(
            id=song_id,
            name=name,
            uri=uri,
            artist_ids=artist_ids,
            sources={source_name},
        )

        songs.append(song)

    return songs
