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

from .. import utils
from ..config import get_global_config
from ..exceptions import *
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


def new_optgroup(name: str, help: str | None = None):
    return optgroup.group(f"\n ❯❯❯ {name}", help=help)


def excepthook(exctype, value, tb):
    """
    Used to patch `sys.excepthook` in order to customize handling of uncaught exceptions.
    """
    # Ignore in-house error types because we don't need a traceback for those.
    if issubclass(exctype, (GantryError, BeakerError)):
        utils.print_stderr(f"[red][bold]{exctype.__name__}:[/] [i]{value}[/][/]")
    # For interruptions, call the original exception handler.
    elif issubclass(exctype, (KeyboardInterrupt, TermInterrupt)):
        sys.__excepthook__(exctype, value, tb)
    else:
        utils.print_stderr(traceback.Traceback.from_exception(exctype, value, tb, suppress=[click]))


sys.excepthook = excepthook


def handle_sigterm(sig, frame):
    del sig, frame
    raise TermInterrupt


config = get_global_config()


@click.group(**CLICK_GROUP_DEFAULTS)  # type: ignore[call-overload]
@click.version_option(version=VERSION)
@click.option(
    "--quiet/--not-quiet",
    help=f"""Don't display the gantry logo.
    Can also be set through the environment variable 'GANTRY_QUIET'.
    {config.get_help_string_for_default('quiet', False)}""",
    envvar="GANTRY_QUIET",
    default=config.quiet if config.quiet is not None else False,
)
@click.option(
    "--check-for-upgrades/--no-check-for-upgrades",
    help="""For check for upgrades or skip checking for upgrades.
    Can also be set through the environment variable 'GANTRY_CHECK_FOR_UPGRADES'.""",
    envvar="GANTRY_CHECK_FOR_UPGRADES",
    default=None,
)
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error"]),
    show_choices=True,
    envvar="GANTRY_LOG_LEVEL",
    help=f"""The Python log level.
    Can also be set through the environment variable 'GANTRY_LOG_LEVEL'.
    {config.get_help_string_for_default('log_level', 'warning')}""",
    default=config.log_level or "warning",
)
def main(quiet: bool = False, check_for_upgrades: bool | None = None, log_level: str = "warning"):
    utils.enable_cli_mode()

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
        handlers=[utils.RichHandler()],
    )

    # Handle SIGTERM just like KeyboardInterrupt
    signal.signal(signal.SIGTERM, handle_sigterm)

    if not quiet:
        utils.print_stderr(
            r'''
[cyan b]                                             o=======[]   [/]
[cyan b]   __ _                    _               _ |_      []   [/]
[cyan b]  / _` |  __ _    _ _     | |_      _ _   | || |     []   [/]
[cyan b]  \__, | / _` |  | ' \    |  _|    | '_|   \_, |   _/ ]_  [/]
[cyan b]  |___/  \__,_|  |_||_|   _\__|   _|_|_   _|__/   |_____| [/]
[blue b]_|"""""|_|"""""|_|"""""|_|"""""|_|"""""|_| """"| [/]
[blue b] `---------------------------------------------' [/]
''',  # noqa: W605
        )

    if check_for_upgrades is not False:
        utils.check_for_upgrades(force=check_for_upgrades is True)
