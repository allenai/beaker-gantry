from typing import Optional

import click
from beaker import Beaker, Job

from .. import util
from ..exceptions import ConfigurationError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("experiment", nargs=1, type=str)
@click.option("-r", "--replica", type=int, help="""The replica rank to pull logs from.""")
def logs(experiment: str, replica: Optional[int] = None):
    """
    Display the logs for an experiment.
    """
    beaker = Beaker.from_env(session=True)

    exp = beaker.experiment.get(experiment)
    tasks = beaker.experiment.tasks(exp)

    job: Job
    if replica is not None:
        for task in tasks:
            if (
                (j := task.latest_job) is not None
                and j.execution is not None
                and j.execution.replica_rank == replica
            ):
                job = j
                break
        else:
            raise ConfigurationError(f"Invalid replica rank '{replica}'")
    else:
        job = beaker.experiment.latest_job(exp)

    job = util.display_logs(beaker, job)
    util.display_results(beaker, exp, job)
