from typing import Optional

import click
from beaker import BeakerJob
from rich import print

from .. import util
from ..exceptions import ConfigurationError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("workload", nargs=1, type=str)
@click.option("-r", "--replica", type=int, help="""The replica rank to pull logs from.""")
@click.option("--task", "task_name", type=str, help="""The name of task to pull logs from.""")
@click.option("-t", "--tail", type=int, help="""Tail this many lines.""")
def logs(
    workload: str,
    replica: Optional[int] = None,
    task_name: Optional[int] = None,
    tail: Optional[int] = None,
):
    """
    Display the logs for an experiment workload.
    """
    if replica is not None and task_name is not None:
        raise ConfigurationError("--replica and --task are mutually exclusive")

    with util.init_client(ensure_workspace=False) as beaker:
        wl = beaker.workload.get(workload)
        tasks = wl.experiment.tasks

        job: Optional[BeakerJob] = None
        if replica is not None:
            for task in tasks:
                j = beaker.workload.get_latest_job(wl, task=task)
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
                    j = beaker.workload.get_latest_job(wl, task=task)
                    if j is None:
                        print("[y]Experiment has not started yet[/]")
                        return
                    else:
                        job = j
                        break
            else:
                raise ConfigurationError(f"Invalid task name '{task_name}'")
        else:
            job = beaker.workload.get_latest_job(wl)

        if job is None:
            print("[y]Experiment has not started yet[/]")
            return

        util.display_logs(beaker, job, tail_lines=tail)
