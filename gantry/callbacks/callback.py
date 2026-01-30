import dataclasses
from dataclasses import dataclass
from typing import Any

from beaker import (
    Beaker,
    BeakerDataset,
    BeakerExperimentSpec,
    BeakerJob,
    BeakerWorkload,
)
from dataclass_extensions import Registrable

from ..exceptions import GantryInterruptWorkload
from ..git_utils import GitRepoState


@dataclass(kw_only=True)
class Callback(Registrable):
    """
    Base class for gantry callbacks. Callbacks provide a way to hook into gantry's launch
    loop to customize behavior on certain events.
    """

    _beaker: Beaker | None = dataclasses.field(repr=False, init=False, default=None)
    _git_repo: GitRepoState | None = dataclasses.field(repr=False, init=False, default=None)
    _spec: BeakerExperimentSpec | None = dataclasses.field(repr=False, init=False, default=None)
    _workload: BeakerWorkload | None = dataclasses.field(repr=False, init=False, default=None)

    @property
    def beaker(self) -> Beaker:
        """
        A beaker client that can be accessed after :meth:`attach()` is called.
        """
        if self._beaker is None:
            raise RuntimeError("Callback has not been attached to a gantry workload yet")
        return self._beaker

    @property
    def git_repo(self) -> GitRepoState:
        """
        The git repo state that can be accessed after :meth:`attach()` is called.
        """
        if self._git_repo is None:
            raise RuntimeError("Callback has not been attached to a gantry workload yet")
        return self._git_repo

    @property
    def spec(self) -> BeakerExperimentSpec:
        """
        The experiment spec that can be accessed after :meth:`attach()` is called.
        """
        if self._spec is None:
            raise RuntimeError("Callback has not been attached to a gantry workload yet")
        return self._spec

    @property
    def workload(self) -> BeakerWorkload:
        """
        The workload that can be accessed after :meth:`attach()` is called.
        """
        if self._workload is None:
            raise RuntimeError("Callback has not been attached to a gantry workload yet")
        return self._workload

    def interrupt_workload(self):
        """Cancels the active workload."""
        raise GantryInterruptWorkload(f"workload interrupted by callback {self.__class__.__name__}")

    def attach(
        self,
        *,
        beaker: Beaker,
        git_repo: GitRepoState,
        spec: BeakerExperimentSpec,
        workload: BeakerWorkload,
    ):
        """
        Runs when a callback is attached to the workload.
        """
        self._beaker = beaker
        self._git_repo = git_repo
        self._spec = spec
        self._workload = workload

    def detach(self):
        """
        Runs when a callback is detached from the workload.
        """
        self._beaker = None
        self._git_repo = None
        self._spec = None
        self._workload = None

    def on_start(self, job: BeakerJob):
        """
        Runs when a job for the workload starts.
        """
        del job

    def on_log(self, job: BeakerJob, log_line: str, log_time: float):
        """
        Runs when a new log event is received from the workload.
        """
        del job, log_line, log_time

    def on_no_new_logs(self, job: BeakerJob):
        """
        Periodically runs when no new logs have been received from the workload recently.
        Runs at most once per second.
        """
        del job

    def on_start_timeout(self, job: BeakerJob):
        """
        Runs when the active job for the workload hits the configured start timeout before starting.
        """
        del job

    def on_timeout(self, job: BeakerJob):
        """
        Runs when the active job for the workload hits the configured timeout before completing.
        """
        del job

    def on_inactive_timeout(self, job: BeakerJob):
        """
        Runs when the active job for the workload hits the configured inactive timeout.
        """
        del job

    def on_inactive_soft_timeout(self, job: BeakerJob):
        """
        Runs when the active job for the workload hits the configured inactive hard timeout.
        """
        del job

    def on_preemption(self, job: BeakerJob):
        """
        Runs when the active job for the workload is preempted.
        """
        del job

    def on_cancellation(self, job: BeakerJob | None):
        """
        Runs when the active job for the workload is canceled by the user, either directly or because.
        a timeout was reached.
        """
        del job

    def on_failure(
        self,
        job: BeakerJob,
        *,
        metrics: dict[str, Any] | None = None,
        results_ds: BeakerDataset | None = None,
    ):
        """
        Runs when the active job for the workload fails.
        """
        del job, metrics, results_ds

    def on_success(
        self,
        job: BeakerJob,
        *,
        metrics: dict[str, Any] | None = None,
        results_ds: BeakerDataset | None = None,
    ):
        """
        Runs when the active job for the workload succeeds.
        """
        del job, metrics, results_ds
