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

from ..git_utils import GitRepoState


@dataclass(kw_only=True)
class Callback(Registrable):
    """
    Base class for gantry callbacks. Callbacks provide a way to hook into the gantry's launch
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

    def attach(
        self,
        *,
        beaker: Beaker,
        git_repo: GitRepoState,
        spec: BeakerExperimentSpec,
        workload: BeakerWorkload,
    ):
        """
        Called when a callback is attached to a gantry workload.
        """
        self._beaker = beaker
        self._git_repo = git_repo
        self._spec = spec
        self._workload = workload

    def detach(self):
        """
        Called when a callback is detached from a gantry workload.
        """
        self._beaker = None
        self._git_repo = None
        self._spec = None
        self._workload = None

    def on_start(self, job: BeakerJob):
        del job

    def on_log(self, job: BeakerJob, log_line: str, log_time: float):
        del job, log_line, log_time

    def on_start_timeout(self, job: BeakerJob):
        del job

    def on_timeout(self, job: BeakerJob):
        del job

    def on_inactive_timeout(self, job: BeakerJob):
        del job

    def on_inactive_soft_timeout(self, job: BeakerJob):
        del job

    def on_preemption(self, job: BeakerJob):
        del job

    def on_cancellation(self, job: BeakerJob | None):
        del job

    def on_failure(
        self,
        job: BeakerJob,
        *,
        metrics: dict[str, Any] | None = None,
        results_ds: BeakerDataset | None = None,
    ):
        del job, metrics, results_ds

    def on_success(
        self,
        job: BeakerJob,
        *,
        metrics: dict[str, Any] | None = None,
        results_ds: BeakerDataset | None = None,
    ):
        del job, metrics, results_ds
