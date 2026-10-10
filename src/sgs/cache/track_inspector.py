"""Builds a plain-text report of everything the cache stores about one track.

The report follows the entities in docs/spotify_cache.md. An empty field is
shown as "(empty)", and a missing row as "(not stored)", so nothing is hidden.
The database is only read, never written.
"""

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from sgs.cache.genre_response_cache import LASTFM_SOURCE, MUSICBRAINZ_SOURCE
from sgs.constants import LIKED_SOURCE_NAME, SAVED_ALBUMS_SOURCE_NAME


def parse_track_id(track_id: str | None, track_link: str | None) -> str:
    """Returns the Spotify track ID from either a bare ID or a link.

    Args:
        track_id (str | None): A bare Spotify track ID.
        track_link (str | None): A Spotify URI or open.spotify.com link to a
            track.

    Returns:
        spotify_id (str): The track ID.

    Raises:
        ValueError: If neither or both of the inputs are given, or the link is
            not a track link.
    """
    if track_link is None:
        if track_id is None:
            raise ValueError("Give either --track-id or --track-link.")

        spotify_id = track_id.strip()

        return spotify_id

    if track_id is not None:
        raise ValueError("Give either --track-id or --track-link, not both.")

    spotify_id = _id_from_link(track_link)

    return spotify_id


def _id_from_link(link: str) -> str:
    """Returns the track ID from a spotify:track URI or an open.spotify.com
    link.

    Args:
        link (str): The URI or link.

    Returns:
        spotify_id (str): The track ID.

    Raises:
        ValueError: If the link does not point to a track.
    """
    if link.startswith("spotify:track:"):
        spotify_id = link.split(":")[-1]

        return spotify_id

    parts = [part for part in urlparse(link).path.split("/") if part]

    if "track" not in parts or parts.index("track") + 1 >= len(parts):
        raise ValueError(f"Not a Spotify track link: {link}")

    spotify_id = parts[parts.index("track") + 1]

    return spotify_id


def open_read_only(db_path: Path) -> sqlite3.Connection:
    """Opens an existing cache database without allowing writes.

    Args:
        db_path (Path): Location of the cache file.

    Returns:
        connection (sqlite3.Connection): Read-only connection to the cache file.

    Raises:
        FileNotFoundError: If the cache file does not exist yet.
    """
    if not db_path.exists():
        raise FileNotFoundError(
            f"No cache database at {db_path}. Run the 'run' command first."
        )

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

    return connection


def _rows(
    connection: sqlite3.Connection, sql: str, params: tuple[str, ...] = ()
) -> list[dict[str, object]]:
    """Runs a query and returns each row as a dictionary keyed by column name.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        sql (str): The query.
        params (tuple[str, ...]): Values for the placeholders in the query.

    Returns:
        rows (list[dict[str, object]]): One dictionary per row.
    """
    cursor = connection.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    fetched = cursor.fetchall()

    rows = []

    for values in fetched:
        pairs = zip(columns, values)
        row = dict(pairs)
        rows.append(row)

    return rows


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    """Checks whether a table exists in the cache database.

    Older cache files may not have the raw tables yet.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        table (str): The table name.

    Returns:
        exists (bool): True if the table is in the database.
    """
    rows = _rows(
        connection,
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    )

    exists = len(rows) > 0

    return exists


def _value(value: object) -> str:
    """Formats one field for the report.

    Args:
        value (object): The stored value.

    Returns:
        text (str): The value, or "(empty)" if there is none.
    """
    if value is None or value == "":
        return "(empty)"

    text = str(value)

    return text


def _fields(row: dict[str, object], keys: list[str], indent: str = "  ") -> list[str]:
    """Lists the given fields of a row, one per line.

    Args:
        row (dict[str, object]): The row to read from.
        keys (list[str]): The column names to show, in order.
        indent (str): The indentation in front of each line.

    Returns:
        lines (list[str]): One line per field.
    """
    lines = []

    for key in keys:
        value = row.get(key)
        lines.append(f"{indent}{key}: {_value(value)}")

    return lines


def _payload_lines(payload: object, include_raw: bool, indent: str) -> list[str]:
    """Describes a stored JSON payload, showing it in full only when asked.

    Args:
        payload (object): The stored JSON text.
        include_raw (bool): Whether to print the full JSON.
        indent (str): The indentation in front of each line.

    Returns:
        lines (list[str]): The lines describing the payload.
    """
    text = str(payload)

    if not include_raw:
        lines = [
            f"{indent}payload: stored, {len(text)} characters (use --raw to show it)"
        ]

        return lines

    pretty = json.dumps(json.loads(text), indent=2)
    body = pretty.splitlines()
    indented = [f"{indent}  {line}" for line in body]
    lines = [f"{indent}payload:", *indented]

    return lines


def _raw_block(
    connection: sqlite3.Connection,
    table: str,
    id_column: str,
    object_id: str,
    include_raw: bool,
    indent: str,
) -> list[str]:
    """Describes the raw copy of one Spotify object.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        table (str): One of the raw tables: raw_tracks, raw_albums, or
            raw_artists.
        id_column (str): The primary key column of that table.
        object_id (str): The Spotify ID of the object.
        include_raw (bool): Whether to print the full JSON.
        indent (str): The indentation in front of each line.

    Returns:
        lines (list[str]): The lines describing the raw copy.
    """
    if not _table_exists(connection, table):
        lines = [
            f"{indent}raw copy: (table {table} does not exist yet, run the 'run' command once)"
        ]

        return lines

    rows = _rows(
        connection,
        f"SELECT fetched_at, payload FROM {table} WHERE {id_column} = ?",
        (object_id,),
    )

    if not rows:
        lines = [f"{indent}raw copy: (not stored)"]

        return lines

    row = rows[0]
    lines = [f"{indent}raw copy:", *_fields(row, ["fetched_at"], indent + "  ")]
    payload_lines = _payload_lines(row["payload"], include_raw, indent + "  ")
    lines.extend(payload_lines)

    return lines


def _genre_response_block(
    connection: sqlite3.Connection,
    artist_id: str,
    source: str,
    include_raw: bool,
    indent: str,
) -> list[str]:
    """Describes the MusicBrainz or Last.fm response stored for one artist.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        artist_id (str): The Spotify artist ID.
        source (str): MUSICBRAINZ_SOURCE or LASTFM_SOURCE.
        include_raw (bool): Whether to print the full JSON.
        indent (str): The indentation in front of each line.

    Returns:
        lines (list[str]): The lines describing the response.
    """
    rows = _rows(
        connection,
        "SELECT source, fetched_at, status, payload FROM artist_genre_responses "
        "WHERE artist_id = ? AND source = ?",
        (artist_id, source),
    )

    lines = [f"{indent}genre response from {source}:"]

    if not rows:
        lines.append(f"{indent}  (not stored)")

        return lines

    row = rows[0]
    lines.extend(_fields(row, ["source", "fetched_at", "status"], indent + "  "))
    lines.extend(_payload_lines(row["payload"], include_raw, indent + "  "))

    return lines


def _heading(title: str) -> list[str]:
    """Returns a blank line and a section title.

    Args:
        title (str): The section title.

    Returns:
        lines (list[str]): The blank line and the title.
    """
    lines = ["", title]

    return lines


def _song_section(
    connection: sqlite3.Connection, song: dict[str, object], include_raw: bool
) -> list[str]:
    """Describes the song row and its raw track copy.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        song (dict[str, object]): The song row, with song_id, name, and uri.
        include_raw (bool): Whether to print the full JSON.

    Returns:
        lines (list[str]): The lines for the song section.
    """
    lines = _heading("Song (songs)")
    lines.extend(_fields(song, ["song_id", "name", "uri"]))
    song_id = str(song["song_id"])
    raw_lines = _raw_block(
        connection, "raw_tracks", "song_id", song_id, include_raw, "  "
    )
    lines.extend(raw_lines)

    return lines


def _artist_section(
    connection: sqlite3.Connection, track_id: str, include_raw: bool
) -> list[str]:
    """Describes each artist of the track, with its genre data.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        track_id (str): The Spotify track ID.
        include_raw (bool): Whether to print the full JSON.

    Returns:
        lines (list[str]): The lines for the artist section.
    """
    rows = _rows(
        connection,
        "SELECT a.artist_id, a.name, sa.position FROM song_artists sa "
        "JOIN artists a ON a.artist_id = sa.artist_id WHERE sa.song_id = ? ORDER BY sa.position",
        (track_id,),
    )

    lines = _heading("Artists (artists, song_artists)")

    if not rows:
        lines.append("  (no artists stored)")

        return lines

    for row in rows:
        artist_id = str(row["artist_id"])
        lines.append(f"  Artist {_value(row['position'])}:")
        lines.extend(_fields(row, ["artist_id", "name", "position"], "    "))
        raw_lines = _raw_block(
            connection, "raw_artists", "artist_id", artist_id, include_raw, "    "
        )
        lines.extend(raw_lines)

        for source in (MUSICBRAINZ_SOURCE, LASTFM_SOURCE):
            response_lines = _genre_response_block(
                connection, artist_id, source, include_raw, "    "
            )
            lines.extend(response_lines)

        genre_rows = _rows(
            connection,
            "SELECT g.genre_name FROM artist_genres ag JOIN genres g ON g.genre_name = ag.genre_name "
            "WHERE ag.artist_id = ?",
            (artist_id,),
        )

        lines.append("    parsed genres (artist_genres):")

        if not genre_rows:
            lines.append("      (none stored, parsing comes later)")

        for genre_row in genre_rows:
            lines.append(f"      {_value(genre_row['genre_name'])}")

    return lines


def _album_section(
    connection: sqlite3.Connection, track_id: str, include_raw: bool
) -> list[str]:
    """Describes each album the track was read from, with its saved-album entry.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        track_id (str): The Spotify track ID.
        include_raw (bool): Whether to print the full JSON.

    Returns:
        lines (list[str]): The lines for the album section.
    """
    rows = _rows(
        connection,
        "SELECT album_id, position FROM album_songs WHERE song_id = ? ORDER BY album_id",
        (track_id,),
    )

    lines = _heading("Albums (album_songs, raw_albums, saved albums in library_items)")

    if not rows:
        lines.append("  (not on any stored album)")

        return lines

    for row in rows:
        album_id = str(row["album_id"])
        lines.append(f"  Album {album_id}:")
        lines.extend(_fields(row, ["album_id", "position"], "    "))
        lines.extend(
            _raw_block(
                connection, "raw_albums", "album_id", album_id, include_raw, "    "
            )
        )
        saved_rows = _rows(
            connection,
            "SELECT source_name, item_id, added_at FROM library_items WHERE source_name = ? AND item_id = ?",
            (SAVED_ALBUMS_SOURCE_NAME, album_id),
        )

        if not saved_rows:
            lines.append("    saved album entry: (not stored)")

            continue

        lines.append("    saved album entry:")
        lines.extend(
            _fields(saved_rows[0], ["source_name", "item_id", "added_at"], "      ")
        )

    return lines


def _playlist_section(connection: sqlite3.Connection, track_id: str) -> list[str]:
    """Describes each stored playlist that contains the track.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        track_id (str): The Spotify track ID.

    Returns:
        lines (list[str]): The lines for the playlist section.
    """
    rows = _rows(
        connection,
        "SELECT p.playlist_id, p.name, p.owner_id, p.collaborative, p.snapshot_id, p.synced_at, "
        "ps.position FROM playlist_songs ps JOIN playlists p ON p.playlist_id = ps.playlist_id "
        "WHERE ps.song_id = ? ORDER BY p.name, ps.position",
        (track_id,),
    )

    lines = _heading("Playlists (playlists, playlist_songs)")

    if not rows:
        lines.append("  (not in any stored playlist)")

        return lines

    for row in rows:
        collaborative = "yes" if row["collaborative"] == 1 else "no"
        row["collaborative"] = collaborative
        lines.append(f"  Playlist {_value(row['name'])}:")
        keys = [
            "playlist_id",
            "name",
            "owner_id",
            "collaborative",
            "snapshot_id",
            "synced_at",
            "position",
        ]
        lines.extend(_fields(row, keys, "    "))

    return lines


def _library_section(connection: sqlite3.Connection, track_id: str) -> list[str]:
    """Describes the liked-songs entry of the track.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        track_id (str): The Spotify track ID.

    Returns:
        lines (list[str]): The lines for the liked-songs section.
    """
    rows = _rows(
        connection,
        "SELECT source_name, item_id, added_at FROM library_items WHERE source_name = ? AND item_id = ?",
        (LIKED_SOURCE_NAME, track_id),
    )

    lines = _heading("Liked songs (library_items)")

    if not rows:
        lines.append("  (not in liked songs)")

        return lines

    lines.extend(_fields(rows[0], ["source_name", "item_id", "added_at"]))

    return lines


def _top_track_section(connection: sqlite3.Connection, track_id: str) -> list[str]:
    """Describes each top-track ranking that contains the track.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        track_id (str): The Spotify track ID.

    Returns:
        lines (list[str]): The lines for the top-tracks section.
    """
    rows = _rows(
        connection,
        "SELECT time_range, position, fetched_at FROM top_track_rankings WHERE song_id = ? "
        "ORDER BY time_range",
        (track_id,),
    )

    lines = _heading("Top tracks (top_track_rankings)")

    if not rows:
        lines.append("  (not in any stored ranking)")

        return lines

    for row in rows:
        lines.append(f"  Ranking {_value(row['time_range'])}:")
        lines.extend(_fields(row, ["time_range", "position", "fetched_at"], "    "))

    return lines


def _source_section(connection: sqlite3.Connection, track_id: str) -> list[str]:
    """Lists the sources the track was read from.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        track_id (str): The Spotify track ID.

    Returns:
        lines (list[str]): The lines for the sources section.
    """
    rows = _rows(
        connection,
        "SELECT source_name FROM song_sources WHERE song_id = ? ORDER BY source_name",
        (track_id,),
    )

    lines = _heading("Sources (song_sources)")

    if not rows:
        lines.append("  (no sources stored)")

        return lines

    for row in rows:
        lines.append(f"  {_value(row['source_name'])}")

    return lines


def build_track_report(
    connection: sqlite3.Connection, track_id: str, include_raw: bool = False
) -> str:
    """Builds the full report for one track.

    Args:
        connection (sqlite3.Connection): Open connection to the cache file.
        track_id (str): The Spotify track ID.
        include_raw (bool): Whether to print the full JSON payloads.

    Returns:
        report (str): The report, ready to print.
    """
    song_rows = _rows(
        connection,
        "SELECT song_id, name, uri FROM songs WHERE song_id = ?",
        (track_id,),
    )

    if not song_rows:
        message = f"No track with ID {track_id} is stored in the cache."

        return message

    lines = _song_section(connection, song_rows[0], include_raw)
    lines.extend(_artist_section(connection, track_id, include_raw))
    lines.extend(_album_section(connection, track_id, include_raw))
    lines.extend(_playlist_section(connection, track_id))
    lines.extend(_library_section(connection, track_id))
    lines.extend(_top_track_section(connection, track_id))
    lines.extend(_source_section(connection, track_id))

    report = "\n".join(lines)

    return report
