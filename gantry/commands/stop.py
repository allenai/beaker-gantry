from typing import List, Optional, Sequence

import click
from beaker import Beaker, Experiment, ExperimentNotFound
from rich import print
from rich.progress import Progress

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
def stop(
    experiment: Sequence[str],
    latest: bool = False,
    workspace: Optional[str] = None,
    dry_run: bool = False,
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
        with Progress(transient=True) as progress:
            task = progress.add_task("Finding latest experiment...", start=False, total=None)
            user = beaker.account.whoami().name
            for exp in beaker.workspace.iter_experiments(workspace=workspace):
                if exp.author.name == user:
                    experiments.append(exp)
                    break
            progress.update(task, completed=True)

    for exp in experiments:
        if dry_run:
            print(f"[b yellow]Dry run:[/] would stop [b cyan]{exp.name}[/]")
        else:
            try:
                beaker.experiment.stop(exp)
            except ExperimentNotFound:
                # Beaker API may return 404 if the experiment was already canceled.
                pass
            print(f"[b green]\N{check mark}[/] [b cyan]{exp.name}[/] stopped")
