import dataclasses
from dataclasses import dataclass
from typing import Literal, Optional

import tomli
from dataclass_extensions import decode


@dataclass
class GantryConfig:
    workspace: Optional[str] = None
    budget: Optional[str] = None
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

        out = decode(cls, data.get("tool", {}).get("gantry", {}))
        out.path = path
        return out

    def get_help_string_for_default(self, field: Literal["workspace", "budget"]) -> str:
        value = getattr(self, field)
        if value is None:
            return ""
        elif self.path is not None:
            return f"Defaults to '{value}' (from config in {self.path})."
        else:
            return f"Defaults to '{value}' (from config)."
