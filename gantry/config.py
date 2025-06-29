import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from gantry.constants import CONFIG_PATH

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

from .exceptions import *


@dataclass
class ProfileConfig:
    """Configuration settings for a single profile."""

    # Image settings
    beaker_image: Optional[str] = None
    docker_image: Optional[str] = None

    # Resource settings
    gpus: Optional[int] = None
    gpu_type: Optional[str] = None
    cluster: Optional[str] = None
    replicas: Optional[int] = None

    # Environment settings
    workspace: Optional[str] = None
    budget: Optional[str] = None
    priority: Optional[str] = None
    preemptible: Optional[bool] = None

    # Python environment
    python_version: Optional[str] = None
    conda_env_file: Optional[str] = None
    pip_requirements_file: Optional[str] = None
    install_command: Optional[str] = None
    no_python: Optional[bool] = None
    no_conda: Optional[bool] = None

    # Experiment settings
    timeout: Optional[int] = None
    show_logs: Optional[bool] = None
    allow_dirty: Optional[bool] = None

    # Additional settings
    env_vars: Dict[str, str] = field(default_factory=dict)
    datasets: Dict[str, str] = field(default_factory=dict)
    weka: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and (not isinstance(v, (dict, list)) or v)}


@dataclass
class GantryConfig:
    """Main configuration object containing all profiles."""

    default_profile: str = "default"
    profiles: Dict[str, ProfileConfig] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "GantryConfig":
        """Load configuration from a TOML file."""
        config_path = path or CONFIG_PATH

        if not config_path.exists():
            # Return empty config
            return cls(profiles={"default": ProfileConfig()})

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            raise ConfigError(f"Failed to load config from {config_path}: {e}")

        config = cls(default_profile=data.get("default_profile", "default"), profiles={})

        profiles_data = data.get("profiles", {})
        for profile_name, profile_data in profiles_data.items():
            config.profiles[profile_name] = ProfileConfig(**profile_data)

        # Ensure default profile exists
        if "default" not in config.profiles:
            config.profiles["default"] = ProfileConfig()

        return config

    def save(self, path: Optional[Path] = None):
        """Save configuration to a TOML file."""
        config_path = path or CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"default_profile": self.default_profile, "profiles": {}}
        for profile_name, profile_config in self.profiles.items():
            profile_dict = profile_config.to_dict()
            if profile_dict:  # Only save non-empty profiles
                data["profiles"][profile_name] = profile_dict

        try:
            with open(config_path, "wb") as f:
                tomli_w.dump(data, f)
        except Exception as e:
            raise ConfigError(f"Failed to save config to {config_path}: {e}")

    def get_profile(self, profile_name: Optional[str] = None) -> ProfileConfig:
        """Get a specific profile or the default profile."""
        name = profile_name or self.default_profile
        if name not in self.profiles:
            raise ConfigError(f"Profile '{name}' not found in configuration")
        return self.profiles[name]

    def set_profile(self, profile_name: str, config: ProfileConfig):
        self.profiles[profile_name] = config

    def list_profiles(self) -> list[str]:
        return list(self.profiles.keys())


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    return CONFIG_PATH


def load_config(path: Optional[Path] = None) -> GantryConfig:
    """Load the Gantry configuration."""
    return GantryConfig.load(path)


def save_config(config: GantryConfig, path: Optional[Path] = None):
    """Save the Gantry configuration."""
    config.save(path)


# TODO: is there a better way to do this? Compare against click defaults?
# lots of special cases and maintenance overhead
def apply_profile_defaults(profile_config: ProfileConfig, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    def apply_profile_default(kwargs_key, profile_attr, condition_func=None, as_tuple=False):
        profile_value = getattr(profile_config, profile_attr, None)
        if profile_value is not None:
            should_apply = condition_func(kwargs) if condition_func else not kwargs.get(kwargs_key)
            if should_apply:
                kwargs[kwargs_key] = (profile_value,) if as_tuple else profile_value

    # Apply profile defaults for simple cases
    # Image settings (mutually exclusive)
    apply_profile_default(
        "beaker_image", "beaker_image", lambda k: k.get("beaker_image") is None and k.get("docker_image") is None
    )
    apply_profile_default(
        "docker_image", "docker_image", lambda k: k.get("beaker_image") is None and k.get("docker_image") is None
    )

    # Resource settings
    apply_profile_default("gpus", "gpus")
    apply_profile_default("gpu_types", "gpu_type", lambda k: not k.get("gpu_types"), as_tuple=True)
    apply_profile_default("clusters", "cluster", lambda k: not k.get("clusters"), as_tuple=True)
    apply_profile_default("replicas", "replicas")

    # Environment settings
    apply_profile_default("workspace", "workspace")
    apply_profile_default("budget", "budget")
    apply_profile_default("priority", "priority")
    apply_profile_default("preemptible", "preemptible")
    apply_profile_default("conda", "conda_env_file")
    apply_profile_default("pip", "pip_requirements_file")
    apply_profile_default("install", "install_command")
    apply_profile_default("no_python", "no_python", lambda k: not k.get("no_python"))
    apply_profile_default("no_conda", "no_conda", lambda k: not k.get("no_conda"))
    apply_profile_default("timeout", "timeout", lambda k: k.get("timeout") == 0)
    apply_profile_default("show_logs", "show_logs", lambda k: k.get("show_logs"))
    apply_profile_default("allow_dirty", "allow_dirty", lambda k: not k.get("allow_dirty"))

    # Handle special cases that require merging
    # Environment variables
    env_vars_list = list(kwargs.get("env_vars", ()))
    for key, value in profile_config.env_vars.items():
        env_vars_list.append(f"{key}={value}")
    if env_vars_list:
        kwargs["env_vars"] = tuple(env_vars_list)

    # Datasets
    datasets_list = list(kwargs.get("datasets", ()))
    for name, mount in profile_config.datasets.items():
        datasets_list.append(f"{name}:{mount}")
    if datasets_list:
        kwargs["datasets"] = tuple(datasets_list)

    # Weka configuration
    weka_list = list(kwargs.get("weka", ()))
    weka_list.extend(profile_config.weka)
    if weka_list:
        kwargs["weka"] = tuple(weka_list)

    return kwargs
