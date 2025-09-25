import json
import logging
import platform
import time
from dataclasses import asdict, dataclass
from datetime import timedelta
from functools import cache
from pathlib import Path
from typing import Optional, cast

import rich
from rich.console import Console

from . import constants
from .exceptions import *
from .version import VERSION

log = logging.getLogger()


VERSION_CHECK_INTERVAL = 12 * 3600  # 12 hours
DEFAULT_INTERNAL_CONFIG_LOCATION: Path | None = None
try:
    DEFAULT_INTERNAL_CONFIG_LOCATION = Path.home() / ".beaker" / ".beaker-gantry.json"
except RuntimeError:
    # Can't locate home directory.
    pass

CLI_MODE = False


def enable_cli_mode():
    global CLI_MODE
    CLI_MODE = True


def is_cli_mode() -> bool:
    return CLI_MODE


@dataclass
class InternalConfig:
    version_checked: float | None = None

    @classmethod
    def load(cls) -> Optional["InternalConfig"]:
        path = DEFAULT_INTERNAL_CONFIG_LOCATION
        if path is None:
            return None
        elif path.is_file():
            try:
                with open(path, "r") as f:
                    return cls(**json.load(f))
            except Exception as e:
                log.exception(
                    f"Loading internal config failed with: {type(e).__name__}: {e}\n"
                    f"If this happens consistently then the config file at '{path}' is probably corrupted and should be deleted.\n"
                    "You can also skip this check by adding the CLI flag '--no-check-for-upgrades' or "
                    "by setting the environment variable 'GANTRY_CHECK_FOR_UPGRADES=0'."
                )
                return None
        else:
            return cls()

    def save(self):
        path = DEFAULT_INTERNAL_CONFIG_LOCATION
        if path is None:
            return None
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            with open(path, "w") as f:
                json.dump(asdict(self), f)


def unique_suffix(max_chars: int = 7) -> str:
    import uuid

    return str(uuid.uuid4())[:max_chars]


def unique_name() -> str:
    import petname

    return cast(str, petname.generate()) + "-" + unique_suffix()


def get_local_python_version() -> str:
    return ".".join(platform.python_version_tuple()[:-1])


def fmt_opt(option: str) -> str:
    if is_cli_mode():
        option = option.strip("-").replace("_", "-")
        return f"'--{option}'"
    else:
        option = option.split("/")[0].strip("- ").replace("-", "_")
        return f"'{option}'"


@cache
def stderr_console() -> Console:
    return Console(stderr=True)


def print_stderr(*args, **kwargs):
    stderr_console().print(*args, **kwargs, highlight=False)


def print_stdout(*args, highlight: bool = False, markup: bool = True, **kwargs):
    rich.get_console().print(*args, **kwargs, highlight=highlight, markup=markup)


def print_exception(*args, **kwargs):
    stderr_console().print_exception(*args, **kwargs)


def format_timedelta(td: "timedelta") -> str:
    def format_value_and_unit(value: int, unit: str) -> str:
        if value == 1:
            return f"{value} {unit}"
        else:
            return f"{value} {unit}s"

    parts = []
    seconds = int(td.total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        parts.append(format_value_and_unit(days, "day"))
    if hours:
        parts.append(format_value_and_unit(hours, "hour"))
    if minutes:
        parts.append(format_value_and_unit(minutes, "minute"))
    if seconds:
        parts.append(format_value_and_unit(seconds, "second"))
    return ", ".join(parts)


def maybe_truncate_text(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    else:
        return s[: n - 1] + "…"


def check_for_upgrades(force: bool = False):
    config = InternalConfig.load()
    if (
        not force
        and config is not None
        and config.version_checked is not None
        and (time.time() - config.version_checked <= VERSION_CHECK_INTERVAL)
    ):
        return

    import packaging.version
    import requests

    try:
        response = requests.get(
            "https://pypi.org/simple/beaker-gantry",
            headers={"Accept": "application/vnd.pypi.simple.v1+json"},
            timeout=2,
        )
        if response.ok:
            latest_version = packaging.version.parse(response.json()["versions"][-1])
            current_version = packaging.version.parse(VERSION)
            if latest_version > current_version and (
                not latest_version.is_prerelease or current_version.is_prerelease
            ):
                print_stderr(
                    f":warning: [yellow]You're using [b]gantry v{VERSION}[/], "
                    f"but a newer version ([b]v{latest_version}[/]) is available: "
                    f"https://github.com/allenai/beaker-gantry/releases/tag/v{latest_version}[/]\n"
                    f"[yellow i]You can upgrade by running:[/] pip install --upgrade beaker-gantry beaker-py\n",
                )
            if config is not None:
                config.version_checked = time.time()
                config.save()
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        pass


def highlight_pattern(s: str, pattern: str) -> str:
    match = s.lower()
    pattern = pattern.lower()
    start_offset = 0
    while (match_start := match.find(pattern, start_offset)) > -1:
        match_str = f"[b green]{pattern.upper()}[/]"
        s = s[:match_start] + match_str + s[match_start + len(pattern) :]
        start_offset = match_start + len(match_str)
        match = s.lower()
    return s


def replace_tags(contents: bytes) -> bytes:
    tag_start = contents.find(b"${{")
    while tag_start != -1:
        tag_end = contents.find(b"}}") + 2
        tag = contents[tag_start:tag_end]
        constant_name = tag.split(b" ")[1].decode()
        contents = contents.replace(tag, getattr(constants, constant_name).encode())  # type: ignore
        tag_start = contents.find(b"${{", tag_end)
    assert b"${{" not in contents
    return contents
