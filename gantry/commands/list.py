from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Generator, List, Optional, Tuple

import click
from beaker import Beaker, Experiment, Task, Tasks
from rich import print
from rich.progress import Progress
from rich.table import Table

from ..exceptions import ConfigurationError
from ..util import StrEnum
from .main import CLICK_COMMAND_DEFAULTS, main


class JobStatus(StrEnum):
    running = "running"
    created = "created"
    scheduled = "scheduled"
    failed = "failed"
    canceled = "canceled"
    succeeded = "succeeded"


class Defaults:
    limit = 10
    max_age = 7


@main.command(name="list", **CLICK_COMMAND_DEFAULTS)
@click.option(
    "-w",
    "--workspace",
    type=str,
    help="""The Beaker workspace to pull experiments from.
    If not specified, your default workspace will be used.""",
)
@click.option(
    "-l",
    "--limit",
    type=int,
    default=Defaults.limit,
    help=f"Limit the number of experiments to display. Default: {Defaults.limit}",
)
@click.option(
    "-a",
    "--author",
    type=str,
    help="Filter by author. Tip: use '--me' instead to show your own experiments.",
)
@click.option(
    "--me",
    is_flag=True,
    help="Only show your own experiments. Mutually exclusive with '--author'.",
)
@click.option(
    "-s",
    "--status",
    type=click.Choice(list(JobStatus)),
    help="Filter by status.",
    multiple=True,
)
@click.option(
    "--max-age",
    type=int,
    default=Defaults.max_age,
    help=f"Maximum age of experiments, in days. Default: {Defaults.max_age}",
)
def list_cmd(
    workspace: Optional[str] = None,
    limit: int = Defaults.limit,
    author: Optional[str] = None,
    me: bool = False,
    status: Optional[List[str]] = None,
    max_age: int = Defaults.max_age,
):
    """
    List gantry experiments.
    """
    beaker = Beaker.from_env(session=True)

    table = Table(title="Experiments", show_lines=True)
    table.add_column("Name", justify="left", no_wrap=True)
    table.add_column("Author", justify="left", style="blue", no_wrap=True)
    table.add_column("Created", justify="left", no_wrap=True)
    table.add_column("Tasks")

    if me:
        if author is not None:
            raise ConfigurationError("--me and -a/--author are mutually exclusive.")
        else:
            author = beaker.account.whoami().name

    with Progress(transient=True) as progress:
        task = progress.add_task("Collecting experiments...", total=limit)
        for exp, tasks in islice(
            iter_experiments(
                beaker, workspace=workspace, author=author, statuses=status, max_age=max_age
            ),
            limit,
        ):
            table.add_row(
                f"[b cyan]{exp.display_name}[/]\n[u i blue]{beaker.experiment.url(exp)}[/]",
                exp.author.name,
                exp.created.astimezone(tz=None).strftime("%I:%M %p on %a, %b %-d"),
                "\n".join(format_task(task) for task in tasks),
            )
            progress.update(task, advance=1)

        progress.update(task, completed=True)

    print(table)


def iter_experiments(
    beaker: Beaker,
    *,
    workspace: Optional[str],
    author: Optional[str],
    statuses: Optional[List[str]],
    max_age: int,
) -> Generator[Tuple[Experiment, Tasks], None, None]:
    now = datetime.now(tz=timezone.utc).astimezone()
    for exp in beaker.workspace.iter_experiments(workspace=workspace):
        # Filter by age.
        age = now - exp.created.astimezone()
        if age > timedelta(days=max_age):
            break

        # Maybe filter by author.
        if author is not None and exp.author.name != author:
            continue

        # Filter out non-gantry experiments.
        spec = beaker.experiment.spec(exp)
        for task_spec in spec.tasks:
            for env_var in task_spec.env_vars or []:
                if env_var.name == "GANTRY_VERSION":
                    break
            else:
                continue

        tasks = beaker.experiment.tasks(exp)

        # Maybe filter by status.
        if statuses:
            for task in tasks:
                if get_status(task) in statuses:
                    break
            else:
                continue

        yield exp, tasks


def get_status(task: Task) -> Optional[JobStatus]:
    job = task.latest_job
    status: Optional[JobStatus] = None
    if job is not None:
        exit_code = job.status.exit_code
        if job.status.current in ("running", "created", "scheduled"):
            status = JobStatus(job.status.current)
        elif job.status.failed is not None or (exit_code is not None and exit_code > 0):
            status = JobStatus.failed
        elif job.status.canceled is not None:
            status = JobStatus.canceled
        elif job.status.finalized is not None and exit_code == 0:
            status = JobStatus.succeeded
    return status


def format_task(task: Task) -> str:
    style = "i"
    status = get_status(task)
    if status in (JobStatus.running, JobStatus.succeeded):
        style += " green"
    elif status in (JobStatus.scheduled, JobStatus.created, JobStatus.canceled):
        style += " yellow"
    elif status == JobStatus.failed:
        style += " red"
    return f"[i]{task.display_name}[/] ([{style}]{status or 'unknown'}[/])"
