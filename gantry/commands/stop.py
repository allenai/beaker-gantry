from typing import List, Optional, Sequence

import click
from beaker import BeakerWorkload
from beaker.exceptions import BeakerWorkloadNotFound
from rich import prompt

from .. import util
from ..exceptions import ConfigurationError, NotFoundError
from ..util import print_stdout as print
from .main import CLICK_COMMAND_DEFAULTS, config, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("workload", nargs=-1, type=str)
@click.option(
    "-l", "--latest", is_flag=True, help="""Stop your latest experiment (non-session) workload."""
)
@click.option(
    "-w",
    "--workspace",
    type=str,
    help=f"""The Beaker workspace to pull experiments from. {config.get_help_string_for_default('workspace')}""",
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
    beaker = util.init_client(ensure_workspace=False)
    workloads: List[BeakerWorkload] = []
    if workload:
        if latest or workspace is not None:
            raise ConfigurationError(
                "[WORKLOAD] args are mutually exclusive with -w/--workspace and -l/--latest"
            )
        for workload_name in workload:
            try:
                workloads.append(beaker.workload.get(workload_name))
            except BeakerWorkloadNotFound:
                raise NotFoundError(f"Workload '{workload_name}' not found")
    else:
        if not latest:
            raise ConfigurationError(
                "A filter such as -l/--latest is required when no [WORKLOAD] is specified"
            )

        wl = util.get_latest_workload(
            beaker, workspace_name=workspace or config.workspace, running=True
        )
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
                f"[b green]\N{check mark}[/] [b cyan]{wl.experiment.name}[/] at [blue u]{beaker.workload.url(wl)}[/] stopped"
            )
