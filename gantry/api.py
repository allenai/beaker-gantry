"""
Gantry's public API.
"""

import time

import rich
from beaker import (
    Beaker,
    BeakerCancelationCode,
    BeakerJob,
    BeakerSortOrder,
    BeakerTask,
    BeakerWorkload,
    BeakerWorkloadStatus,
)
from rich.status import Status

from .exceptions import *
from .git_utils import GitRepoState

__all__ = ["GitRepoState", "follow_workload"]


def _wait_for_job_to_start(
    *,
    beaker: Beaker,
    job: BeakerJob,
    status: Status,
    start_time: float,
    timeout: int = 0,
    show_logs: bool = True,
) -> BeakerJob:
    # Pull events until job is running (or fails)...
    events = set()
    while not (job.status.HasField("finalized") or (show_logs and job.status.HasField("started"))):
        if timeout > 0 and (time.monotonic() - start_time) > timeout:
            raise BeakerJobTimeoutError(f"Timed out while waiting for job '{job.id}' to finish")

        for event in beaker.job.list_summarized_events(
            job, sort_order=BeakerSortOrder.descending, sort_field="latest_occurrence"
        ):
            event_hashable = (event.latest_occurrence.ToSeconds(), event.latest_message)
            if event_hashable not in events:
                status.update(f"[i]{event.latest_message}[/]")
                events.add(event_hashable)
                time.sleep(0.5)

        time.sleep(0.5)
        job = beaker.job.get(job.id)

    return job


def _job_preempted(job: BeakerJob) -> bool:
    return job.status.status == BeakerWorkloadStatus.canceled and job.status.canceled_code in (
        BeakerCancelationCode.system_preemption,
        BeakerCancelationCode.user_preemption,
    )


def follow_workload(
    beaker: Beaker,
    workload: BeakerWorkload,
    *,
    task: BeakerTask | None = None,
    timeout: int = 0,
    tail: bool = False,
    show_logs: bool = True,
) -> BeakerJob:
    """
    Follow a workload until completion while streaming logs to stdout.

    :param task: A specific task in the workload to follow. Defaults to the first task.
    :param timeout: The number of seconds to wait for the workload to complete. Raises a timeout
        error if it doesn't complete in time. Set to 0 (the default) to wait indefinitely.
    :param tail: Start tailing the logs if a job is already running. Otherwise shows all logs.
    :param show_logs: Set to ``False`` to avoid streaming the logs.

    :returns: The finalized :class:`~beaker.types.BeakerJob` from the task being followed.

    :raises ~gantry.exceptions.BeakerJobTimeoutError: If ``timeout`` is set to a positive number
        and the workload doesn't complete in time.
    """
    console = rich.get_console()
    start_time = time.monotonic()
    preempted_job_ids = set()

    while True:
        with console.status("[i]waiting...[/]", spinner="point", speed=0.8) as status:
            # Wait for job to be created...
            job: BeakerJob | None = None
            while job is None:
                if (
                    j := beaker.workload.get_latest_job(workload, task=task)
                ) is not None and j.id not in preempted_job_ids:
                    job = j
                else:
                    time.sleep(1.0)

            # Wait for job to start...
            job = _wait_for_job_to_start(
                beaker=beaker,
                job=job,
                status=status,
                start_time=start_time,
                timeout=timeout,
                show_logs=show_logs,
            )

        # Stream logs...
        if show_logs and job.status.HasField("started"):
            print()
            rich.get_console().rule("Logs")

            for job_log in beaker.job.logs(job, tail_lines=10 if tail else None, follow=True):
                console.print(job_log.message.decode(), highlight=False, markup=False)
                if timeout > 0 and (time.monotonic() - start_time) > timeout:
                    raise BeakerJobTimeoutError(
                        f"Timed out while waiting for job '{job.id}' to finish"
                    )

            print()
            rich.get_console().rule("End logs")
            print()

        # Wait for job to finalize...
        while not job.status.HasField("finalized"):
            time.sleep(0.5)
            job = beaker.job.get(job.id)

        # If job was preempted, we start over...
        if _job_preempted(job):
            print(f"[yellow]Job '{job.id}' preempted.[/] ")
            preempted_job_ids.add(job.id)
            continue

        return job
