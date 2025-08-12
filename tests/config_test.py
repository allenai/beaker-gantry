from gantry.config import GantryConfig


def test_load_config():
    config = GantryConfig.load()  # loads from pyproject.toml
    assert isinstance(config, GantryConfig)
    assert config.workspace == "ai2/gantry-testing"
    assert config.budget == "ai2/oe-base"
