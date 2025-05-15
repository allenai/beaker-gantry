import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Generator, Iterable, List, Optional, Tuple

import click
import rich
from beaker import (
    Beaker,
    BeakerSortOrder,
    BeakerTask,
    BeakerWorkload,
    BeakerWorkloadStatus,
    BeakerWorkloadType,
)
from beaker.exceptions import BeakerGroupNotFound
from rich import print
from rich.table import Table

from .. import util
from ..exceptions import ConfigurationError
from .main import CLICK_COMMAND_DEFAULTS, main


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
@click.option("-g", "--group", type=str, help="""The Beaker group to pull experiments from.""")
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
    type=click.Choice([x.name for x in BeakerWorkloadStatus]),
    help="Filter by status. Multiple allowed.",
    multiple=True,
)
@click.option(
    "--max-age",
    type=int,
    default=Defaults.max_age,
    help=f"Maximum age of experiments, in days. Default: {Defaults.max_age}",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all experiments, not just onces submitted through Gantry.",
)
def list_cmd(
    workspace: Optional[str] = None,
    group: Optional[str] = None,
    limit: int = Defaults.limit,
    author: Optional[str] = None,
    me: bool = False,
    status: Optional[List[str]] = None,
    max_age: int = Defaults.max_age,
    show_all: bool = False,
):
    """
    List recent experiments within a workspace or group.
    This will only show experiments launched with Gantry by default, unless '--all' is specified.
    """
    with util.init_client(ensure_workspace=False) as beaker:
        table = Table(title="Experiments", show_lines=True)
        table.add_column("Name", justify="left", no_wrap=True)
        table.add_column("Author", justify="left", style="blue", no_wrap=True)
        table.add_column("Created", justify="left", no_wrap=True)
        table.add_column("Tasks")

        if me:
            if author is not None:
                raise ConfigurationError("--me and -a/--author are mutually exclusive.")
            else:
                author = beaker.user_name

        status_msg = "[i]collecting experiments...[/]"
        with rich.get_console().status(status_msg, spinner="point", speed=0.8) as status_:
            with ThreadPoolExecutor() as executor:
                for wl, tasks in islice(
                    iter_workloads(
                        beaker,
                        executor=executor,
                        workspace=workspace,
                        group=group,
                        author=author,
                        statuses=status,
                        max_age=max_age,
                        show_all=show_all,
                        limit=None if not show_all else limit,
                    ),
                    limit,
                ):
                    status_.update(f"{status_msg} [cyan]{wl.experiment.name}[/]")

                    task_status_futures = []
                    for task in tasks:
                        task_status_futures.append(executor.submit(format_task, beaker, wl, task))

                    task_statuses = {}
                    for task_future in concurrent.futures.as_completed(task_status_futures):
                        task, task_status = task_future.result()
                        task_statuses[task.id] = task_status
                        status_.update(f"{status_msg} [cyan]{wl.experiment.name} ❯ [/]{task.name}")

                    table.add_row(
                        f"[b cyan]{wl.experiment.name}[/]\n[u i blue]{beaker.workload.url(wl)}[/]",
                        beaker.user.get(wl.experiment.author_id).name,
                        wl.experiment.created.ToDatetime(timezone.utc)
                        .astimezone(tz=None)
                        .strftime("%I:%M %p on %a, %b %-d"),
                        "\n".join(task_statuses[task.id] for task in tasks),
                    )

        print(table)


def is_gantry_workload(beaker: Beaker, wl: BeakerWorkload) -> bool:
    spec = beaker.experiment.get_spec(wl.experiment)
    for task_spec in spec.tasks:
        for env_var in task_spec.env_vars or []:
            if env_var.name == "GANTRY_VERSION":
                return True
    return False


def iter_workloads(
    beaker: Beaker,
    *,
    executor: ThreadPoolExecutor,
    workspace: Optional[str],
    group: Optional[str],
    author: Optional[str],
    statuses: Optional[List[str]],
    max_age: int,
    show_all: bool,
    limit: Optional[int] = None,
) -> Generator[Tuple[BeakerWorkload, Iterable[BeakerTask]], None, None]:
    created_after = datetime.now(tz=timezone.utc).astimezone() - timedelta(days=max_age)
    author_id = None if author is None else beaker.user.get(author)
    workload_statuses = (
        None if not statuses else [BeakerWorkloadStatus.from_any(s) for s in statuses]
    )

    if group is not None:
        beaker_group = util.resolve_group(
            beaker, group, workspace, fall_back_to_default_workspace=False
        )
        if beaker_group is None:
            raise BeakerGroupNotFound(group)

        # Will have to sort workloads manually by creation time, so we gather them all first.
        workload_futures = []
        for task_metrics in beaker.group.list_task_metrics(beaker_group):
            workload_futures.append(
                executor.submit(beaker.workload.get, task_metrics.experiment_id)
            )

        workloads = []
        for future in concurrent.futures.as_completed(workload_futures):
            wl = future.result()

            # Filter out non-gantry experiments.
            if not show_all and not is_gantry_workload(beaker, wl):
                continue

            if author_id is not None and wl.experiment.author_id != author_id:
                continue

            if workload_statuses is not None and wl.status not in workload_statuses:
                continue

            if wl.experiment.created.ToDatetime(timezone.utc) < created_after:
                continue

            workloads.append(wl)

        workloads.sort(key=lambda wl: wl.experiment.created.ToMilliseconds(), reverse=True)
        for wl in workloads:
            yield wl, wl.experiment.tasks
    else:
        for wl in beaker.workload.list(
            workspace=None if workspace is None else beaker.workspace.get(workspace),
            author=author_id,
            created_after=created_after,
            workload_type=BeakerWorkloadType.experiment,
            statuses=workload_statuses,
            sort_order=BeakerSortOrder.descending,
            sort_field="created",
            limit=limit,
        ):
            # Filter out non-gantry experiments.
            if not show_all and not is_gantry_workload(beaker, wl):
                continue

            yield wl, wl.experiment.tasks


def get_status(
    beaker: Beaker, wl: BeakerWorkload, task: BeakerTask
) -> Optional[BeakerWorkloadStatus]:
    job = beaker.workload.get_latest_job(wl, task=task)
    if job is not None:
        return BeakerWorkloadStatus.from_any(job.status.status)
    else:
        return None


def format_task(beaker: Beaker, wl: BeakerWorkload, task: BeakerTask) -> tuple[BeakerTask, str]:
    style = "i"
    status = get_status(beaker, wl, task)
    if status in (
        BeakerWorkloadStatus.running,
        BeakerWorkloadStatus.succeeded,
        BeakerWorkloadStatus.uploading_results,
        BeakerWorkloadStatus.ready_to_start,
        BeakerWorkloadStatus.initializing,
    ):
        style += " green"
    elif status in (
        BeakerWorkloadStatus.submitted,
        BeakerWorkloadStatus.queued,
        BeakerWorkloadStatus.canceled,
        BeakerWorkloadStatus.stopping,
    ):
        style += " yellow"
    elif status == BeakerWorkloadStatus.failed:
        style += " red"

    status_str = "unknown" if status is None else status.name

    return task, f"[i]{task.name}[/] ([{style}]{status_str}[/])"
