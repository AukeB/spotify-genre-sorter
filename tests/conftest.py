"""Module conftest.py, reusable code for pytest."""


from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from unittest.mock import patch, mock_open
from pathlib import Path

from sgs.config.config_manager import ConfigManager

@pytest.fixture(scope="function", name="mock_yaml_content")
def mock_yaml_config():
    """Fixture that defines a mock config content"""
    yaml_content = """
        sources:
            liked_songs: true
            saved_albums: false
            top_tracks: false
            your_playlists: true
        options:
            top_tracks_time_range: long_term
            include_collaborative_playlists: false
    """

    return yaml_content


@pytest.fixture(scope="function", name="mock_config")
def test_load_conig_file(mock_yaml_content):
    """Test loading config using mocked open."""
    m_open = mock_open(read_data=mock_yaml_content)

    with patch("sgs.config.config_manager.open", m_open):
        config_manager = ConfigManager(Path("mock_config_path.yaml"))
        config = config_manager.load_config_file()

    return config

@pytest.fixture(scope="function", name="cache_path")
def fixture_cache_path(tmp_path, monkeypatch):
    """Points the Spotify cache at a temporary file for one test."""
    path = tmp_path / "spotify_cache.db"
    monkeypatch.setattr("sgs.spotify_cache.CACHE_DB_PATH", path)

    return path


CACHE_SPOTIFY_MODULES = [
    "sgs.cache.playlist_cache",
    "sgs.cache.library_cache",
    "sgs.cache.top_track_cache",
]


def _serve_pages(responses):
    """Returns a stand-in for get_all_pages that serves items keyed by URL."""

    def fake(url, access_token, params=None, description=None):
        items = list(responses.get(url, []))

        return items

    return fake


def _serve_total(responses):
    """Returns a stand-in for fetch_total that counts the items served for a URL."""

    def fake(url, access_token):
        total = len(responses.get(url, []))

        return total

    return fake


@pytest.fixture(scope="function", name="spotify_calls")
def fixture_spotify_calls(monkeypatch):
    """Serves Spotify responses to the cache, keyed by URL, and records the calls.

    Call the returned function with a dict of responses. It returns an object
    with the mocks as `pages` (get_all_pages) and `total` (fetch_total).
    """

    def install(responses):
        pages = MagicMock(side_effect=_serve_pages(responses))
        total = MagicMock(side_effect=_serve_total(responses))

        for module in CACHE_SPOTIFY_MODULES:
            monkeypatch.setattr(f"{module}.get_all_pages", pages)

        monkeypatch.setattr("sgs.cache.library_cache.fetch_total", total)

        calls = SimpleNamespace(pages=pages, total=total)

        return calls

    return install


@pytest.fixture(scope="function", autouse=True, name="no_rate_limit")
def fixture_no_rate_limit(monkeypatch):
    """Stops the rate limiter from sleeping, so tests of external APIs run fast."""
    monkeypatch.setattr("sgs.utils.rate_limiter.time.sleep", lambda seconds: None)

