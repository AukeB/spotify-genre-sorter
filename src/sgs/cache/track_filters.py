"""Filters for track objects from Spotify."""

from collections.abc import Iterable


def usable_tracks(items: Iterable[dict | None]) -> list[dict]:
    """Returns the track objects that have an ID, skipping null entries.

    Args:
        items (Iterable[dict | None]): Track objects from Spotify. Null entries
            are allowed.

    Returns:
        tracks (list[dict]): The usable track objects, in the same order.
    """

    tracks = []

    for track in items:
        if track is None or track.get("id") is None:
            continue

        tracks.append(track)

    return tracks
