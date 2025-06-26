from typing import Optional

import click
from beaker import Beaker, BeakerJob, BeakerTask, BeakerWorkload
from rich import print

from .. import util
from ..exceptions import ConfigurationError
from .main import CLICK_COMMAND_DEFAULTS, main


def _get_job(
    beaker: Beaker, wl: BeakerWorkload, task: BeakerTask, run: Optional[int] = None
) -> Optional[BeakerJob]:
    if run is None:
        return beaker.workload.get_latest_job(wl, task=task)
    else:
        # NOTE: ascending sort order on creation time is not implemented server-side yet
        jobs = list(reversed(list(beaker.job.list(task=task, sort_field="created"))))
        try:
            return jobs[run - 1]
        except IndexError:
            raise ConfigurationError(f"run number {run} does not exist")


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("workload", nargs=1, type=str)
@click.option("-r", "--replica", type=int, help="""The replica rank to pull logs from.""")
@click.option("--task", "task_name", type=str, help="""The name of task to pull logs from.""")
@click.option("-t", "--tail", type=int, help="""Tail this many lines.""")
@click.option("--run", type=int, help="""The run number to pull logs from.""")
@click.option(
    "-f", "--follow", is_flag=True, help="""Continue streaming logs for the duration of the job."""
)
def logs(
    workload: str,
    replica: Optional[int] = None,
    task_name: Optional[int] = None,
    tail: Optional[int] = None,
    run: Optional[int] = None,
    follow: bool = False,
):
    """
    Display the logs for an experiment workload.
    """
    if replica is not None and task_name is not None:
        raise ConfigurationError("--replica and --task are mutually exclusive")

    if run is not None and run < 1:
        raise ConfigurationError("--run must be at least 1")

    with util.init_client(ensure_workspace=False) as beaker:
        wl = beaker.workload.get(workload)
        tasks = list(wl.experiment.tasks)

        job: Optional[BeakerJob] = None
        task: Optional[BeakerTask] = None
        if replica is not None:
            for task in tasks:
                job = _get_job(beaker, wl, task, run=run)
                if job is not None and job.system_details.replica_group_details.rank == replica:
                    break
            else:
                raise ConfigurationError(f"Invalid replica rank '{replica}'")
        elif task_name is not None:
            for task in tasks:
                if task.name == task_name:
                    job = _get_job(beaker, wl, task, run=run)
                    break
            else:
                raise ConfigurationError(f"Invalid task name '{task_name}'")
        else:
            task = tasks[0]
            job = _get_job(beaker, wl, task, run=run)

        if job is None:
            print("[yellow]Experiment has not started yet[/]")
            return

        print(f"Showing logs from job '{job.id}' for task '{task.name}'...")
        util.display_logs(beaker, job, tail_lines=tail, follow=follow)
