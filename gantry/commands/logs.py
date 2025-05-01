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
@click.option("-t", "--tail", type=int, help="""Tail this many lines.""")
def logs(workload: str, replica: Optional[int] = None, tail: Optional[int] = None):
    """
    Display the logs for an experiment workload.
    """
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
        else:
            job = beaker.workload.get_latest_job(wl)

        if job is None:
            print("[y]Experiment has not started yet[/]")
            return

        util.display_logs(beaker, job, tail_lines=tail)
