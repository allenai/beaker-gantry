import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import click
from beaker import Beaker, BeakerJob, BeakerTask, BeakerWorkload

from .. import beaker_utils, utils
from ..aliases import PathOrStr
from ..exceptions import ConfigurationError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("workload", nargs=1, type=str)
@click.option("-r", "--replica", type=int, help="""The replica rank to pull logs from.""")
@click.option("--task", "task_name", type=str, help="""The name of task to pull logs from.""")
@click.option("--run", type=int, help="""The run number to pull logs from.""")
@click.option(
    "-a",
    "--all",
    "all_tasks",
    is_flag=True,
    help="""Pull logs from all tasks/replicas.
    This requires an output directory (e.g. --output=~/Downloads/).""",
)
@click.option("-n", "--head", type=int, help="""Only download the first N lines.""")
@click.option("-t", "--tail", type=int, help="""Tail this many lines.""")
@click.option("-s", "--since", type=str, help="""Only pull logs since this time (ISO format).""")
@click.option(
    "-f", "--follow", is_flag=True, help="""Continue streaming logs for the duration of the job."""
)
@click.option("-o", "--output", type=str, help="""A file or directory to download the logs to.""")
def logs(
    workload: str,
    replica: int | None = None,
    task_name: int | None = None,
    run: int | None = None,
    all_tasks: bool = False,
    head: int | None = None,
    tail: int | None = None,
    since: str | None = None,
    follow: bool = False,
    output: PathOrStr | None = None,
):
    """
    Download the logs from a workload.
    """
    if sum([replica is not None, task_name is not None, all_tasks]) > 1:
        raise ConfigurationError("--replica, --task, and --all are mutually exclusive")

    if all_tasks and follow:
        raise ConfigurationError("--all and --follow are mutually exclusive")

    if run is not None and run < 1:
        raise ConfigurationError("--run must be at least 1")

    if tail and since:
        raise ConfigurationError("--tail and --since are mutually exclusive")

    if head and tail:
        raise ConfigurationError("--head and --tail are mutually exclusive")

    if output is not None:
        output = Path(output)

    since_dt: datetime | None = None
    if since is not None:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")) - timedelta(milliseconds=1)

    with beaker_utils.init_client(ensure_workspace=False) as beaker:
        wl = beaker.workload.get(workload)
        tasks = list(wl.experiment.tasks)

        job: BeakerJob | None = None
        task: BeakerTask | None = None
        out_path: Path | None = None
        if all_tasks:
            if output is None:
                raise ConfigurationError(
                    "An --output directory must be provided when pulling logs from all tasks/replicas"
                )
            elif not output.is_dir() and output.suffix:
                raise ConfigurationError(
                    "--output must be a directory when pulling logs from all tasks/replicas"
                )

            if wl.experiment.id and wl.experiment.id not in str(output):
                output = output / wl.experiment.id

            utils.print_stdout(f"Pulling logs from {len(tasks):,d} tasks/replicas...")
            with ThreadPoolExecutor() as executor:
                futures = []
                for task in tasks:
                    out_path = _resolve_output_file_path(output, task, run)
                    future = executor.submit(
                        _resolve_job_and_download_logs,
                        beaker,
                        wl=wl,
                        task=task,
                        run=run,
                        head=head,
                        tail=tail,
                        since=since_dt,
                        out_path=out_path,
                    )
                    futures.append(future)

                num_log_files_written = 0
                min_lines_logged: int | None = None
                file_with_min_lines: Path | None = None
                max_lines_logged: int | None = None
                file_with_max_lines: Path | None = None
                for future in concurrent.futures.as_completed(futures):
                    task, job, out_path, n_lines = future.result()
                    assert task is not None
                    if job is None:
                        utils.print_stderr(
                            f"[yellow]Job for task '{task.name}' has not started yet[/]"
                        )
                    else:
                        num_log_files_written += 1
                        if min_lines_logged is None or n_lines < min_lines_logged:
                            min_lines_logged = n_lines
                            file_with_min_lines = out_path
                        if max_lines_logged is None or n_lines > max_lines_logged:
                            max_lines_logged = n_lines
                            file_with_max_lines = out_path

            if num_log_files_written > 0:
                utils.print_stdout(f"Logs saved to [cyan]{output}[/]")

            if (
                num_log_files_written > 1
                and min_lines_logged is not None
                and file_with_min_lines is not None
            ):
                utils.print_stdout(
                    f"Log file with fewest lines: [cyan]{file_with_min_lines}[/] ({min_lines_logged:,d} lines)"
                )

            if (
                num_log_files_written > 1
                and max_lines_logged is not None
                and file_with_max_lines is not None
            ):
                utils.print_stdout(
                    f"Log file with most lines: [cyan]{file_with_max_lines}[/] ({max_lines_logged:,d} lines)"
                )
        else:
            if replica is not None:
                for task in tasks:
                    job = beaker_utils.get_job(beaker, wl, task, run=run)
                    if job is not None and job.system_details.replica_group_details.rank == replica:
                        break
                else:
                    raise ConfigurationError(f"Invalid replica rank '{replica}'")
            elif task_name is not None:
                for task in tasks:
                    if task.name == task_name:
                        job = beaker_utils.get_job(beaker, wl, task, run=run)
                        break
                else:
                    raise ConfigurationError(f"Invalid task name '{task_name}'")
            else:
                task = tasks[0]
                job = beaker_utils.get_job(beaker, wl, task, run=run)

            if job is None:
                utils.print_stderr("[yellow]Experiment has not started yet[/]")
                return

            if output is not None:
                out_path = _resolve_output_file_path(output, task, run)

            utils.print_stdout(f"Pulling logs from job '{job.id}' for task '{task.name}'...")
            beaker_utils.download_logs(
                beaker,
                job,
                head_lines=head,
                tail_lines=tail,
                follow=follow,
                since=since_dt,
                out_path=out_path,
            )

            if out_path is not None:
                utils.print_stdout(f"Logs saved to [cyan]{out_path}[/]")


def _resolve_output_file_path(output: Path, task: BeakerTask, run: int | None) -> Path:
    if output.is_dir() or not output.suffix:
        if run is not None:
            return output / f"{task.name}-run-{run}.log"
        else:
            return output / f"{task.name}.log"
    else:
        return output


def _resolve_job_and_download_logs(
    beaker: Beaker,
    *,
    wl: BeakerWorkload,
    task: BeakerTask,
    run: int | None,
    out_path: Path,
    head: int | None = None,
    tail: int | None = None,
    since: datetime | None = None,
) -> tuple[BeakerTask, BeakerJob | None, Path, int]:
    job = beaker_utils.get_job(beaker, wl, task, run=run)
    if job is None:
        return task, None, out_path, 0
    job, n_lines = beaker_utils.download_logs(
        beaker,
        job,
        head_lines=head,
        tail_lines=tail,
        follow=False,
        since=since,
        out_path=out_path,
    )
    return task, job, out_path, n_lines
