"""Module for running the main repository workflow."""

import yaml

from src.my_project.config_manager import ConfigManager

def main() -> None:
    """
    Load configuration and print the loaded settings.

    1. Instantiate ConfigManager and load the config file.
    2. Print the loaded configuration as YAML.
    """
    config_manager = ConfigManager()
    config = config_manager.load_config_file()

    print("Loaded config:")
    print(yaml.safe_dump(config.model_dump(), sort_keys=False, default_flow_style=False))


if __name__ == "__main__":
    main()