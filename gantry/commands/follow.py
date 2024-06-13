from typing import Optional

import click
from beaker import Beaker, Experiment
from rich import print

from .. import util
from ..exceptions import ConfigurationError, NotFoundError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("experiment", nargs=1, required=False, type=str)
@click.option(
    "-t", "--tail", is_flag=True, help="Only tail the logs as opposed to printing all logs so far."
)
@click.option(
    "-l", "--latest", is_flag=True, help="Get the logs from the latest running experiment."
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
    help="Pull the latest experiment for a particular author. Defaults to your own account.",
)
def follow(
    experiment: Optional[str] = None,
    tail: bool = False,
    latest: bool = False,
    workspace: Optional[str] = None,
    author: Optional[str] = None,
):
    """
    Follow the logs for a running experiment.
    """
    beaker = Beaker.from_env(session=True)

    exp: Optional[Experiment] = None
    if experiment is not None:
        if latest or workspace is not None or author is not None:
            raise ConfigurationError(
                "EXPERIMENT is mutually exclusive with -a/--author, -w/--workspace, and -l/--latest"
            )
        exp = beaker.experiment.get(experiment)
    else:
        if not latest:
            raise ConfigurationError(
                "A filter such as -l/--latest is required when no [EXPERIMENT] is specified"
            )

        exp = util.get_latest_experiment(beaker, author=author, workspace=workspace, running=True)
        if exp is None:
            raise NotFoundError("Failed to find an experiment to follow")

        print(
            f"Following experiment [b cyan]{exp.name}[/] ({exp.id}) at {beaker.experiment.url(exp)}"
        )

    assert exp is not None
    job = util.follow_experiment(beaker, exp, tail=tail)
    util.display_results(beaker, exp, job)
