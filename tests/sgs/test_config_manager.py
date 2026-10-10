"""Module for testing config_manager.py"""


from sgs.config_manager import ConfigModel


# Testing the "load_config_file" method from the "ConfigManager" class.


def test_load_config_file(mock_config):
    """Testing the 'load_config_file' method."""
    assert isinstance(mock_config, ConfigModel)
    assert mock_config.config_category_1.float_param == 1.5