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
def logs(
    workload: str,
    replica: Optional[int] = None,
    task_name: Optional[int] = None,
    tail: Optional[int] = None,
    run: Optional[int] = None,
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
        if replica is not None:
            for task in tasks:
                j = _get_job(beaker, wl, task, run=run)
                if j is None:
                    print("[y]Experiment has not started yet[/]")
                    return

                if j.system_details.replica_group_details.rank == replica:
                    job = j
                    break
            else:
                raise ConfigurationError(f"Invalid replica rank '{replica}'")
        elif task_name is not None:
            for task in tasks:
                if task.name == task_name:
                    j = _get_job(beaker, wl, task, run=run)
                    if j is None:
                        print("[y]Experiment has not started yet[/]")
                        return
                    else:
                        job = j
                        break
            else:
                raise ConfigurationError(f"Invalid task name '{task_name}'")
        else:
            j = _get_job(beaker, wl, tasks[0], run=run)

        if job is None:
            print("[y]Experiment has not started yet[/]")
            return

        util.display_logs(beaker, job, tail_lines=tail)
