from typing import List, Optional, Sequence

import click
from beaker import BeakerWorkload
from beaker.exceptions import BeakerWorkloadNotFound
from rich import print, prompt

from .. import util
from ..exceptions import ConfigurationError, NotFoundError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("workload", nargs=-1, type=str)
@click.option(
    "-l", "--latest", is_flag=True, help="""Stop your latest experiment (non-session) workload."""
)
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
    workload: Sequence[str],
    latest: bool = False,
    workspace: Optional[str] = None,
    dry_run: bool = False,
    yes: bool = False,
):
    """
    Stop a running workload.
    """
    if workload and latest:
        raise ConfigurationError("-l/--latest is mutually exclusive with [WORKLOAD] args")

    beaker = util.init_client(ensure_workspace=False)

    workloads: List[BeakerWorkload] = []
    if workload:
        for workload_name in workload:
            try:
                workloads.append(beaker.workload.get(workload_name))
            except BeakerWorkloadNotFound:
                raise NotFoundError(f"Workload '{workload_name}' not found")
    elif latest:
        wl = util.get_latest_workload(beaker, workspace_name=workspace, running=True)
        if wl is None:
            print("[yellow]No running workloads to stop[/]")
        else:
            workloads.append(wl)

    for wl in workloads:
        if dry_run:
            print(f"[b yellow]Dry run:[/] would stop [b cyan]{wl.experiment.name}[/]")
        else:
            if not yes and not prompt.Confirm.ask(
                f"Stop experiment [b cyan]{wl.experiment.name}[/] at [blue u]{beaker.workload.url(wl)}[/]?"
            ):
                print("[yellow]Skipping experiment...[/]")
                continue

            try:
                beaker.workload.cancel(wl)
            except (BeakerWorkloadNotFound,):
                pass
            print(
                f"[b green]\N{check mark}[/] [b cyan]{wl.experiment.name}[/] at {beaker.workload.url(wl)} stopped"
            )
