"""Module for loading the configuration files."""

import yaml

from pathlib import Path

from src.my_project.constants import CONFIG_PATH
from src.my_project.config_model import ConfigModel


class ConfigManager:
    """Loads and validates configuration files into a ConfigModel.

    Handles reading a YAML config file from disk and parsing it into a validated
    Pydantic model.
    """

    def __init__(self, config_path: Path = CONFIG_PATH) -> None:
        """Initializes the ConfigManager with a path to the config file.

        Args:
            config_path (Path): Path to the YAML configuration file to load.
        """
        self.config_path = config_path

    def load_config_file(self) -> ConfigModel:
        """Reads the YAML config file and parses it into a ConfigModel.

        1. Opens the config file at self.config_path.
        2. Parses the file contents as YAML.
        3. Validates and structures the parsed data into a ConfigModel.

        Returns:
            config (ConfigModel): The validated configuration object.
        """
        with open(self.config_path) as file:
            config = yaml.safe_load(file)

        return ConfigModel(**config)
