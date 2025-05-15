import logging
import os
import signal
import sys

import click
import rich
from beaker.exceptions import BeakerError
from click_help_colors import HelpColorsCommand, HelpColorsGroup
from click_option_group import optgroup
from rich import pretty, traceback
from rich.logging import RichHandler

from .. import util
from ..exceptions import *
from ..util import print_stderr
from ..version import VERSION

CLICK_GROUP_DEFAULTS = {
    "cls": HelpColorsGroup,
    "help_options_color": "green",
    "help_headers_color": "yellow",
    "context_settings": {"max_content_width": 115},
}

CLICK_COMMAND_DEFAULTS = {
    "cls": HelpColorsCommand,
    "help_options_color": "green",
    "help_headers_color": "yellow",
    "context_settings": {"max_content_width": 115},
}


def new_optgroup(name: str):
    return optgroup.group(f"\n ❯❯❯ {name}")


def excepthook(exctype, value, tb):
    """
    Used to patch `sys.excepthook` in order to customize handling of uncaught exceptions.
    """
    # Ignore in-house error types because we don't need a traceback for those.
    if issubclass(exctype, (GantryError, BeakerError)):
        print_stderr(f"[red][bold]{exctype.__name__}:[/] [i]{value}[/][/]")
    # For interruptions, call the original exception handler.
    elif issubclass(exctype, (KeyboardInterrupt, TermInterrupt)):
        sys.__excepthook__(exctype, value, tb)
    else:
        print_stderr(traceback.Traceback.from_exception(exctype, value, tb, suppress=[click]))


sys.excepthook = excepthook


def handle_sigterm(sig, frame):
    del sig, frame
    raise TermInterrupt


@click.group(**CLICK_GROUP_DEFAULTS)  # type: ignore[call-overload]
@click.version_option(version=VERSION)
@click.option(
    "--quiet",
    is_flag=True,
    help="Don't display the gantry logo.",
)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"]),
    show_choices=True,
    show_default=True,
    default="warning",
    help="The Python log level.",
)
def main(quiet: bool = False, log_level: str = "warning"):
    # Configure rich.
    if os.environ.get("GANTRY_GITHUB_TESTING"):
        # Force a broader terminal when running tests in GitHub Actions.
        console_width = 180
        rich.reconfigure(width=console_width, force_terminal=True, force_interactive=False)
        pretty.install()
    else:
        pretty.install()

    # Configure logging.
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
        handlers=[RichHandler(log_time_format="❯ [GANTRY (local)] [%X]")],
    )

    # Handle SIGTERM just like KeyboardInterrupt
    signal.signal(signal.SIGTERM, handle_sigterm)

    if not quiet:
        print_stderr(
            r'''
[cyan b]                                             o=======[]   [/]
[cyan b]   __ _                    _               _ |_      []   [/]
[cyan b]  / _` |  __ _    _ _     | |_      _ _   | || |     []   [/]
[cyan b]  \__, | / _` |  | ' \    |  _|    | '_|   \_, |   _/ ]_  [/]
[cyan b]  |___/  \__,_|  |_||_|   _\__|   _|_|_   _|__/   |_____| [/]
[blue b]_|"""""|_|"""""|_|"""""|_|"""""|_|"""""|_| """"| [/]
[blue b] `---------------------------------------------' [/]
''',  # noqa: W605
            highlight=False,
        )

    util.check_for_upgrades()
