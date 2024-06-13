from typing import List, Optional, Sequence

import click
from beaker import Beaker, Experiment, ExperimentConflict, ExperimentNotFound
from rich import print, prompt

from .. import util
from ..exceptions import ConfigurationError, NotFoundError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("experiment", nargs=-1, type=str)
@click.option("-l", "--latest", is_flag=True, help="""Stop your latest experiment.""")
@click.option(
    "-w",
    "--workspace",
    type=str,
    help="""The Beaker workspace to pull experiments from.
    If not specified, your default workspace will be used.""",
)
@click.option("--dry-run", is_flag=True, help="Do a dry-run without stopping any experiments.")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="""Skip all confirmation prompts.""",
)
def stop(
    experiment: Sequence[str],
    latest: bool = False,
    workspace: Optional[str] = None,
    dry_run: bool = False,
    yes: bool = False,
):
    """
    Stop a running experiment.
    """
    if experiment and latest:
        raise ConfigurationError("-l/--latest is mutually exclusive with [EXPERIMENT] args")

    beaker = Beaker.from_env(session=True)

    experiments: List[Experiment] = []
    if experiment:
        for experiment_name in experiment:
            try:
                experiments.append(beaker.experiment.get(experiment_name))
            except ExperimentNotFound:
                raise NotFoundError(f"Experiment '{experiment_name}' not found")
    elif latest:
        exp = util.get_latest_experiment(beaker, workspace=workspace, running=True)
        if exp is None:
            print("[yellow]No running experiments to stop[/]")
        else:
            experiments.append(exp)

    for exp in experiments:
        if dry_run:
            print(f"[b yellow]Dry run:[/] would stop [b cyan]{exp.name}[/]")
        else:
            if not yes and not prompt.Confirm.ask(
                f"Stop experiment [b cyan]{exp.name}[/] at [blue u]{beaker.experiment.url(exp)}[/]?"
            ):
                print("[yellow]Skipping experiment...[/]")
                continue

            try:
                beaker.experiment.stop(exp)
            except (ExperimentNotFound, ExperimentConflict):
                # Beaker API may return 404 if the experiment was already canceled.
                pass
            print(
                f"[b green]\N{check mark}[/] [b cyan]{exp.name}[/] at {beaker.experiment.url(exp)} stopped"
            )
