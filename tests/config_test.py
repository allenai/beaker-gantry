import tempfile
from pathlib import Path

import pytest

from gantry import config as gantry_config
from gantry.exceptions import ConfigError


def test_profile_config_to_dict():
    config = gantry_config.ProfileConfig(
        beaker_image="ai2/test",
        gpus=2,
        env_vars={"KEY": "value"},
        weka=["oe-training-default:/weka/oe-training-default", "oe-adapt-default:/weka/oe-adapt-default"],
    )

    d = config.to_dict()

    assert d == {
        "beaker_image": "ai2/test",
        "gpus": 2,
        "env_vars": {"KEY": "value"},
        "weka": ["oe-training-default:/weka/oe-training-default", "oe-adapt-default:/weka/oe-adapt-default"],
    }
    assert "docker_image" not in d
    assert "cluster" not in d


def test_gantry_config_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.toml"

        config = gantry_config.GantryConfig(
            default_profile="training",
            profiles={
                "default": gantry_config.ProfileConfig(beaker_image="ai2/conda", workspace="default-ws"),
                "training": gantry_config.ProfileConfig(
                    beaker_image="ai2/pytorch",
                    gpus=8,
                    cluster="ai2/jupiter",
                    env_vars={"CUDA_VISIBLE_DEVICES": "0,1,2,3,4,5,6,7"},
                    weka=["oe-training-default:/weka/oe-training-default", "oe-adapt-default:/weka/oe-adapt-default"],
                ),
            },
        )

        config.save(config_path)

        loaded = gantry_config.GantryConfig.load(config_path)

        assert loaded.default_profile == "training"
        assert len(loaded.profiles) == 2
        assert loaded.profiles["default"].beaker_image == "ai2/conda"
        assert loaded.profiles["training"].gpus == 8
        assert loaded.profiles["training"].env_vars["CUDA_VISIBLE_DEVICES"] == "0,1,2,3,4,5,6,7"
        assert loaded.profiles["training"].weka == [
            "oe-training-default:/weka/oe-training-default",
            "oe-adapt-default:/weka/oe-adapt-default",
        ]


def test_gantry_config_get_profile():
    config = gantry_config.GantryConfig(
        default_profile="default",
        profiles={
            "default": gantry_config.ProfileConfig(
                beaker_image="ai2/conda",
                workspace="default-ws",
                gpus=1,
                weka=["oe-training-default:/weka/oe-training-default", "oe-adapt-default:/weka/oe-adapt-default"],
            ),
            "training": gantry_config.ProfileConfig(
                gpus=8, cluster="ai2/jupiter", weka=["oe-training-default:/weka/oe-training-default"]
            ),
        },
    )

    default = config.get_profile()
    assert default.beaker_image == "ai2/conda"
    assert default.gpus == 1
    assert default.weka == [
        "oe-training-default:/weka/oe-training-default",
        "oe-adapt-default:/weka/oe-adapt-default",
    ]

    training = config.get_profile("training")
    assert training.beaker_image is None  # Not set in training profile
    assert training.workspace is None  # Not set in training profile
    assert training.gpus == 8
    assert training.cluster == "ai2/jupiter"
    assert training.weka == ["oe-training-default:/weka/oe-training-default"]

    with pytest.raises(ConfigError):
        config.get_profile("nonexistent")


def test_gantry_config_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nonexistent.toml"

        config = gantry_config.GantryConfig.load(config_path)

        assert config.default_profile == "default"
        assert "default" in config.profiles
        assert len(config.profiles) == 1


def test_gantry_config_list_profiles():
    config = gantry_config.GantryConfig(
        profiles={
            "default": gantry_config.ProfileConfig(),
            "training": gantry_config.ProfileConfig(),
            "inference": gantry_config.ProfileConfig(),
        }
    )

    profiles = config.list_profiles()
    assert set(profiles) == {"default", "training", "inference"}
