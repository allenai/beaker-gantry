from concurrent.futures import ThreadPoolExecutor

import click
from beaker import Beaker, BeakerJob, BeakerSortOrder
from rich import print

from .. import util
from ..exceptions import ConfigurationError
from .main import CLICK_COMMAND_DEFAULTS, main


def _pull_logs(beaker: Beaker, job: BeakerJob, lines: int) -> str:
    logs = []
    for job_log in beaker.job.logs(job, tail_lines=lines, follow=False):
        logs.append(job_log.message.decode(errors="ignore"))
    return "\n".join(logs)


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("workload", nargs=1, type=str)
@click.option("--run", type=int, help="""The run number to pull logs from.""")
@click.option(
    "-l", "--lines", type=int, help="""The number of latest log lines to check.""", default=100
)
def analyze_logs(
    workload: str,
    run: int = 1,
    lines: int = 100,
):
    """
    Analyze the logs from a multi-task / multi-replica job to find problematic nodes.
    """
    with util.init_client(ensure_workspace=False) as beaker:
        wl = beaker.workload.get(workload)
        tasks = list(wl.experiment.tasks)
        if len(tasks) <= 1:
            raise ConfigurationError("Workload must have multiple tasks/replicas")

        logs_per_task = {}
        for task in tasks:
            jobs = list(
                reversed(
                    list(
                        beaker.job.list(
                            task=task,
                            sort_field="created",
                            sort_order=BeakerSortOrder.descending,  # ascending not supported for creation time yet
                        )
                    )
                )
            )
            if not jobs:
                raise ConfigurationError(f"No jobs found for task '{task.name}'")
            elif len(jobs) < run:
                raise ConfigurationError(
                    f"Invalid run number. Task '{task.name}' only has {len(jobs)} run(s)."
                )

            job = jobs[run - 1]
            logs = _pull_logs(beaker, job, lines)
            logs_per_task[task.name] = logs
