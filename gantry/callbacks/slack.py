from dataclasses import dataclass
from typing import Any

import requests
from beaker import BeakerDataset, BeakerJob

from .callback import Callback


@Callback.register("slack")
@dataclass(kw_only=True)
class SlackCallback(Callback):
    webhook_url: str

    @property
    def workload_name(self) -> str:
        return f"{self.beaker.user_name}/{self.workload.experiment.name}"

    @property
    def workload_url(self) -> str:
        return self.beaker.workload.url(self.workload)

    def on_start(self, job: BeakerJob):
        del job
        requests.post(
            self.webhook_url,
            json={
                "text": f":check: Workload <{self.workload_url}|*{self.workload_name}*> has started! :runner:"
            },
        )

    def on_start_timeout(self, job: BeakerJob):
        del job
        requests.post(
            self.webhook_url,
            json={
                "text": f":warning: Workload <{self.workload_url}|*{self.workload_name}*> failed to start in time!"
            },
        )

    def on_timeout(self, job: BeakerJob):
        del job
        requests.post(
            self.webhook_url,
            json={
                "text": f":warning: Workload <{self.workload_url}|*{self.workload_name}*> failed to complete in time!"
            },
        )

    def on_inactive_timeout(self, job: BeakerJob):
        del job
        requests.post(
            self.webhook_url,
            json={
                "text": f":zzz: Workload <{self.workload_url}|*{self.workload_name}*> appears to be inactive!"
            },
        )

    def on_inactive_soft_timeout(self, job: BeakerJob):
        del job
        requests.post(
            self.webhook_url,
            json={
                "text": f":zzz: Workload <{self.workload_url}|*{self.workload_name}*> appears to be inactive!"
            },
        )

    def on_preemption(self, job: BeakerJob):
        del job
        requests.post(
            self.webhook_url,
            json={
                "text": f":warning: Workload <{self.workload_url}|*{self.workload_name}*> was preempted!"
            },
        )

    def on_cancellation(self, job: BeakerJob | None):
        del job
        requests.post(
            self.webhook_url,
            json={
                "text": f":warning: Workload <{self.workload_url}|*{self.workload_name}*> was canceled!"
            },
        )

    def on_failure(
        self,
        job: BeakerJob,
        *,
        metrics: dict[str, Any] | None = None,
        results_ds: BeakerDataset | None = None,
    ):
        del job, metrics, results_ds
        requests.post(
            self.webhook_url,
            json={
                "text": f":check-failed: Workload <{self.workload_url}|*{self.workload_name}*> failed!"
            },
        )

    def on_success(
        self,
        job: BeakerJob,
        *,
        metrics: dict[str, Any] | None = None,
        results_ds: BeakerDataset | None = None,
    ):
        del job, metrics, results_ds
        requests.post(
            self.webhook_url,
            json={
                "text": f":check: Workload <{self.workload_url}|*{self.workload_name}*> succeeded!"
            },
        )
