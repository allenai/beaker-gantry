import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import click
from beaker import BeakerJob, BeakerTask

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
    tail: int | None = None,
    since: str | None = None,
    follow: bool = False,
    output: PathOrStr | None = None,
):
    """
    Display the logs for an experiment workload.
    """
    if sum([replica is not None, task_name is not None, all_tasks]) > 1:
        raise ConfigurationError("--replica, --task, and --all are mutually exclusive")

    if all_tasks and follow:
        raise ConfigurationError("--all and --follow are mutually exclusive")

    if run is not None and run < 1:
        raise ConfigurationError("--run must be at least 1")

    if tail and since:
        raise ConfigurationError("--tail and --since are mutually exclusive")

    if output is not None:
        output = Path(output)

    since_dt: datetime | None = None
    if since is not None:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))

    with beaker_utils.init_client(ensure_workspace=False) as beaker:
        wl = beaker.workload.get(workload)
        tasks = list(wl.experiment.tasks)

        job: BeakerJob | None = None
        task: BeakerTask | None = None
        if all_tasks:
            if output is None:
                raise ConfigurationError(
                    "An --output directory must be provided when pulling logs from all tasks/replicas"
                )
            elif output.is_file() or output.suffix:
                raise ConfigurationError(
                    "--output must be a directory when pulling logs from all tasks/replicas"
                )

            all_jobs: list[BeakerJob] = []
            for task in tasks:
                job = beaker_utils.get_job(beaker, wl, task, run=run)
                if job is None:
                    utils.print_stderr("[yellow]Experiment has not started yet[/]")
                    return
                else:
                    all_jobs.append(job)

            utils.print_stdout(f"Pulling logs from all {len(tasks):,d} tasks/replicas...")
            with ThreadPoolExecutor() as executor:
                futures = []
                for job, task in zip(all_jobs, tasks):
                    out_path = (
                        None if output is None else _resolve_output_file_path(output, task, run)
                    )
                    future = executor.submit(
                        beaker_utils.download_logs,
                        beaker,
                        job,
                        tail_lines=tail,
                        follow=False,
                        since=since_dt,
                        out_path=out_path,
                    )
                    futures.append(future)
                for future in concurrent.futures.as_completed(futures):
                    future.result()

            utils.print_stdout(f"Logs saved to [cyan]{output}[/]")
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

            out_path = None if output is None else _resolve_output_file_path(output, task, run)

            utils.print_stdout(f"Pulling logs from job '{job.id}' for task '{task.name}'...")
            beaker_utils.download_logs(
                beaker,
                job,
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
