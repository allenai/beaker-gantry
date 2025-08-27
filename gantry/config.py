import dataclasses
from dataclasses import dataclass
from typing import Any, Literal, Optional

import tomli
from dataclass_extensions import decode

from .exceptions import ConfigurationError


@dataclass
class GantryConfig:
    workspace: Optional[str] = None
    gh_token_secret: Optional[str] = None
    budget: Optional[str] = None
    log_level: Optional[Literal["debug", "info", "warning", "error"]] = None
    quiet: Optional[bool] = None
    path: Optional[str] = dataclasses.field(repr=False, default=None)

    @classmethod
    def load(cls) -> "GantryConfig":
        """
        Load configuration from a ``pyproject.toml`` under the ``[tool.gantry]`` section.
        """
        path = "pyproject.toml"
        try:
            with open(path, "rb") as f:
                data = tomli.load(f)
            assert isinstance(data, dict)
        except FileNotFoundError:
            return cls()

        try:
            out = decode(cls, data.get("tool", {}).get("gantry", {}))
        except Exception as e:
            raise ConfigurationError(
                f"Failed to decode gantry config from {path} ({type(e).__name__}: {e})"
            ) from e

        out.path = path
        return out

    def _get_value_string(self, value: Any) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        else:
            return f"'{value}'"

    def get_help_string_for_default(
        self,
        field: Literal["workspace", "gh_token_secret", "budget", "log_level", "quiet"],
        default: Any = None,
    ) -> str:
        value = getattr(self, field)
        if value is None and default is None:
            return ""
        elif value is None:
            return f"Defaults to {self._get_value_string(default)}."
        elif self.path is not None:
            return f"Defaults to {self._get_value_string(value)} (from config in {self.path})."
        else:
            return f"Defaults to {self._get_value_string(value)} (from config)."
