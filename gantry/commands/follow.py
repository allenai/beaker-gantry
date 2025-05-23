from typing import Optional

import click
from beaker import BeakerWorkload
from rich import print

from .. import util
from ..api import follow_workload
from ..exceptions import ConfigurationError, NotFoundError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("workload", nargs=1, required=False, type=str)
@click.option(
    "-t", "--tail", is_flag=True, help="Only tail the logs as opposed to printing all logs so far."
)
@click.option(
    "-l",
    "--latest",
    is_flag=True,
    help="Get the logs from the latest running experiment (non-session) workload.",
)
@click.option(
    "-w",
    "--workspace",
    type=str,
    help="""The Beaker workspace to pull experiments from.
    If not specified, your default workspace will be used.""",
)
@click.option(
    "-a",
    "--author",
    type=str,
    help="Pull the latest experiment workload for a particular author. Defaults to your own account.",
)
def follow(
    workload: Optional[str] = None,
    tail: bool = False,
    latest: bool = False,
    workspace: Optional[str] = None,
    author: Optional[str] = None,
):
    """
    Follow the logs for a running experiment.
    """
    with util.init_client(ensure_workspace=False) as beaker:
        wl: Optional[BeakerWorkload] = None
        if workload is not None:
            if latest or workspace is not None or author is not None:
                raise ConfigurationError(
                    "[WORKLOAD] is mutually exclusive with -a/--author, -w/--workspace, and -l/--latest"
                )
            wl = beaker.workload.get(workload)
        else:
            if not latest:
                raise ConfigurationError(
                    "A filter such as -l/--latest is required when no [WORKLOAD] is specified"
                )

            wl = util.get_latest_workload(
                beaker, author_name=author, workspace_name=workspace, running=True
            )
            if wl is None:
                raise NotFoundError("Failed to find an experiment workload to follow")

            print(
                f"Following experiment [b cyan]{wl.experiment.name}[/] ({wl.experiment.id}) at {beaker.workload.url(wl)}"
            )

        assert wl is not None
        job = follow_workload(beaker, wl, tail=tail)
        util.display_results(beaker, wl, job)
