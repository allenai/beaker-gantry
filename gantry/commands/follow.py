import click
from beaker import BeakerWorkload

from .. import beaker_utils, utils
from ..config import get_global_config
from ..exceptions import ConfigurationError, NotFoundError
from ..launch import follow_workload
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
    help=f"""The Beaker workspace to pull experiments from. {get_global_config().get_help_string_for_default('workspace')}""",
)
@click.option(
    "-a",
    "--author",
    type=str,
    help="Pull the latest experiment workload for a particular author. Defaults to your own account.",
)
def follow(
    workload: str | None = None,
    tail: bool = False,
    latest: bool = False,
    workspace: str | None = None,
    author: str | None = None,
):
    """
    Follow a workload.
    """
    with beaker_utils.init_client(ensure_workspace=False) as beaker:
        wl: BeakerWorkload | None = None
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

            wl = beaker_utils.get_latest_workload(
                beaker,
                author_name=author,
                workspace_name=workspace or get_global_config().workspace,
                running=True,
            )
            if wl is None:
                raise NotFoundError("Failed to find an experiment workload to follow")

            utils.print_stdout(
                f"Following experiment [b cyan]{wl.experiment.name}[/] ({wl.experiment.id}) at [blue u]{beaker.workload.url(wl)}[/]"
            )

        assert wl is not None
        job = beaker.workload.get_latest_job(wl)
        job = follow_workload(beaker, wl, job=job, tail=tail)
        beaker_utils.display_results(beaker, wl, job)
