import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Generator, Iterable

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
from rich.table import Table

from .. import beaker_utils, utils
from ..config import get_global_config
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
    help=f"""The Beaker workspace to pull experiments from. {get_global_config().get_help_string_for_default('workspace')}""",
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
    "-t",
    "--text",
    "name_or_description",
    type=str,
    help="Filter by text in the experiment name or description.",
)
@click.option(
    "--max-age",
    "max_age_str",
    type=str,
    default=Defaults.max_age,
    help=f"""Maximum age of experiments (in days, by default).
    Can also be specified as a duration such as '5m', '2h', etc.
    Default: {Defaults.max_age} days.""",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all experiments, not just onces submitted through Gantry.",
)
def list_cmd(
    workspace: str | None = None,
    group: str | None = None,
    limit: int = Defaults.limit,
    author: str | None = None,
    me: bool = False,
    status: list[str] | None = None,
    name_or_description: str | None = None,
    max_age_str: str = str(Defaults.max_age),
    show_all: bool = False,
):
    """
    List workloads within a workspace or group.
    This will only show workloads launched with Gantry by default, unless '--all' is specified.
    """
    max_age: timedelta
    try:
        max_age = timedelta(days=int(max_age_str))
    except ValueError:
        max_age = utils.parse_timedelta(max_age_str)

    with beaker_utils.init_client(ensure_workspace=False) as beaker:
        table = Table(title="Experiments", show_lines=True)
        table.add_column("Workload", justify="left", no_wrap=True)
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
                        name_or_description=name_or_description,
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
                        f"[b cyan]{wl.experiment.name}[/]\n"
                        f"[blue u]{beaker.workload.url(wl)}[/]\n"
                        f"{utils.maybe_truncate_text(wl.experiment.description, max(len(beaker.workload.url(wl)), len(wl.experiment.name)))}".strip(),
                        beaker.user.get(wl.experiment.author_id).name,
                        wl.experiment.created.ToDatetime(timezone.utc)
                        .astimezone(tz=None)
                        .strftime("%I:%M %p on %a, %b %-d"),
                        "\n".join(task_statuses[task.id] for task in tasks),
                    )

        utils.print_stdout(table)


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
    workspace: str | None,
    group: str | None,
    author: str | None,
    statuses: list[str] | None,
    name_or_description: str | None,
    max_age: timedelta,
    show_all: bool,
    limit: int | None = None,
) -> Generator[tuple[BeakerWorkload, Iterable[BeakerTask]], None, None]:
    created_after = datetime.now(tz=timezone.utc).astimezone() - max_age
    author_id = None if author is None else beaker.user.get(author)
    workload_statuses = (
        None if not statuses else [BeakerWorkloadStatus.from_any(s) for s in statuses]
    )

    if group is not None:
        beaker_group = beaker_utils.resolve_group(
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

            if (
                name_or_description is not None
                and name_or_description not in wl.experiment.name
                and name_or_description not in wl.experiment.description
            ):
                continue

            workloads.append(wl)

        workloads.sort(key=lambda wl: wl.experiment.created.ToMilliseconds(), reverse=True)
        for wl in workloads:
            yield wl, wl.experiment.tasks
    else:
        if workspace is None:
            workspace = get_global_config().workspace

        for wl in beaker.workload.list(
            workspace=None if workspace is None else beaker.workspace.get(workspace),
            author=author_id,
            created_after=created_after,
            workload_type=BeakerWorkloadType.experiment,
            statuses=workload_statuses,
            name_or_description=name_or_description,
            sort_order=BeakerSortOrder.descending,
            sort_field="created",
            limit=limit,
        ):
            # Filter out non-gantry experiments.
            if not show_all and not is_gantry_workload(beaker, wl):
                continue

            yield wl, wl.experiment.tasks


def get_status(beaker: Beaker, wl: BeakerWorkload, task: BeakerTask) -> BeakerWorkloadStatus | None:
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
