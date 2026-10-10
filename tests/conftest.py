"""Module conftest.py, reusable code for pytest."""


import pytest
from unittest.mock import patch, mock_open
from pathlib import Path

from sgs.config_manager import ConfigManager

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

    with patch("sgs.config_manager.open", m_open):
        config_manager = ConfigManager(Path("mock_config_path.yaml"))
        config = config_manager.load_config_file()

    return config