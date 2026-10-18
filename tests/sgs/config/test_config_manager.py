"""Module for testing config/config_manager.py"""


from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from pydantic import ValidationError

from sgs.config.config_manager import ConfigManager, ConfigModel


# Testing the "load_config_file" method from the "ConfigManager" class.


def test_load_config_file(mock_config):
    """Testing the 'load_config_file' method."""
    assert isinstance(mock_config, ConfigModel)
    assert mock_config.sources.liked_songs is True
    assert mock_config.sources.saved_albums is False
    assert mock_config.sources.top_tracks is False
    assert mock_config.sources.your_playlists is True
    assert mock_config.options.top_tracks_time_range == "long_term"
    assert mock_config.options.include_collaborative_playlists is False


# Testing the "load_config_file" method from the "ConfigManager" class with an invalid option.


def test_load_config_file_rejects_unknown_time_range(mock_yaml_content):
    """A time range outside the allowed values fails validation."""
    yaml_text = mock_yaml_content.replace("long_term", "forever")
    m_open = mock_open(read_data=yaml_text)

    with patch("sgs.config.config_manager.open", m_open), pytest.raises(ValidationError):
        config_path = Path("mock_config_path.yaml")
        config_manager = ConfigManager(config_path)
        config_manager.load_config_file()
