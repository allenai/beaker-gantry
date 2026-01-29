import json
import logging
import platform
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Literal, Optional, cast

import rich
from rich.console import Console, ConsoleRenderable
from rich.text import Text
from rich.traceback import Traceback

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


def is_interactive_terminal() -> bool:
    return rich.get_console().is_interactive and rich.get_console().is_terminal


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


def parse_timedelta(dur: str) -> timedelta:
    dur_normalized = dur.replace(" ", "").lower()
    if not re.match(r"^(([0-9.e-]+)([a-z]*))+$", dur_normalized):
        raise ValueError(f"invalid duration string '{dur}'")

    seconds = 0.0
    for match in re.finditer(r"([0-9.e-]+)([a-z]*)", dur_normalized):
        value_str, unit = match.group(1), match.group(2)
        try:
            value = float(value_str)
        except ValueError:
            raise ValueError(f"invalid duration string '{dur}'")

        if not unit:
            # assume seconds
            unit = "s"

        if unit in ("ns", "nanosecond", "nanoseconds"):
            # nanoseconds
            seconds += value / 1_000_000_000
        elif unit in ("µs", "microsecond", "microseconds"):
            seconds += value / 1_000_000
        elif unit in ("ms", "millisecond", "milliseconds"):
            # milliseconds
            seconds += value / 1_000
        elif unit in ("s", "sec", "second", "seconds"):
            # seconds
            seconds += value
        elif unit in ("m", "min", "minute", "minutes"):
            # minutes
            seconds += value * 60
        elif unit in ("h", "hr", "hour", "hours"):
            # hours
            seconds += value * 3_600
        elif unit in ("d", "day", "days"):
            # days
            seconds += value * 86_400
        else:
            raise ValueError(f"invalid duration string '{dur}'")

    return timedelta(seconds=seconds)


def format_timedelta(
    td: timedelta | float, resolution: Literal["seconds", "minutes"] = "seconds"
) -> str:
    if isinstance(td, float):
        td = timedelta(seconds=td)

    def format_value_and_unit(value: int, unit: str) -> str:
        if value == 1:
            return f"{value} {unit}"
        else:
            return f"{value} {unit}s"

    seconds = int(td.total_seconds())
    if resolution == "minutes":
        seconds = round(seconds / 60) * 60

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days:
        parts.append(format_value_and_unit(days, "day"))
    if hours:
        parts.append(format_value_and_unit(hours, "hour"))
    if minutes:
        parts.append(format_value_and_unit(minutes, "minute"))
    if seconds:
        parts.append(format_value_and_unit(seconds, "second"))

    if not parts:
        if resolution == "minutes":
            parts.append("under 1 minute")
        else:
            parts.append("under 1 second")

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


def import_module(module_name: str):
    import importlib

    return importlib.import_module(module_name)


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


class RichHandler(logging.Handler):
    """
    A simplified version of rich.logging.RichHandler from
    https://github.com/Textualize/rich/blob/master/rich/logging.py
    """

    def __init__(
        self,
        *,
        level: int | str = logging.NOTSET,
        console: Optional[Console] = None,
        markup: bool = False,
    ) -> None:
        super().__init__(level=level)
        self.console = console or rich.get_console()
        self.markup = markup

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if hasattr(record.msg, "__rich__") or hasattr(record.msg, "__rich_console__"):
                self.console.print(record.msg)
            else:
                msg: Any = record.msg
                if isinstance(record.msg, str):
                    msg = self.render_message(record=record, message=record.getMessage())
                renderables = [
                    self.get_time_text(record),
                    self.get_level_text(record),
                    self.get_location_text(record),
                    msg,
                ]
                if record.exc_info is not None:
                    tb = Traceback.from_exception(*record.exc_info)  # type: ignore
                    renderables.append(tb)
                self.console.print(*renderables)
        except Exception:
            self.handleError(record)

    def render_message(self, *, record: logging.LogRecord, message: str) -> ConsoleRenderable:
        use_markup = getattr(record, "markup", self.markup)
        message_text = Text.from_markup(message) if use_markup else Text(message)
        return message_text

    def get_time_text(self, record: logging.LogRecord) -> Text:
        log_time = datetime.fromtimestamp(record.created)
        time_str = log_time.strftime("[%Y-%m-%d %X]")
        return Text(time_str, style="log.time", end=" ")

    def get_level_text(self, record: logging.LogRecord) -> Text:
        level_name = record.levelname
        level_text = Text.styled(level_name.ljust(8), f"logging.level.{level_name.lower()}")
        level_text.style = "log.level"
        level_text.end = " "
        return level_text

    def get_location_text(self, record: logging.LogRecord) -> Text:
        name_and_line = f"{record.name}:{record.lineno}" if record.name != "root" else "root"
        text = f"[{name_and_line}]"  # type: ignore
        return Text(text, style="log.path")
