import click
from beaker import BeakerJob, BeakerTask

from .. import beaker_utils, utils
from ..exceptions import ConfigurationError
from .main import CLICK_COMMAND_DEFAULTS, main


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
    replica: int | None = None,
    task_name: int | None = None,
    tail: int | None = None,
    run: int | None = None,
    follow: bool = False,
):
    """
    Display the logs for an experiment workload.
    """
    if replica is not None and task_name is not None:
        raise ConfigurationError("--replica and --task are mutually exclusive")

    if run is not None and run < 1:
        raise ConfigurationError("--run must be at least 1")

    with beaker_utils.init_client(ensure_workspace=False) as beaker:
        wl = beaker.workload.get(workload)
        tasks = list(wl.experiment.tasks)

        job: BeakerJob | None = None
        task: BeakerTask | None = None
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
            utils.print_stdout("[yellow]Experiment has not started yet[/]")
            return

        utils.print_stdout(f"Showing logs from job '{job.id}' for task '{task.name}'...")
        beaker_utils.display_logs(beaker, job, tail_lines=tail, follow=follow)
