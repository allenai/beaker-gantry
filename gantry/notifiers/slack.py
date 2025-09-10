import requests
from beaker import Beaker, BeakerJob, BeakerWorkload

from .notifier import Event, Notifier


class SlackNotifier(Notifier):
    def __init__(self, beaker: Beaker, webhook_url: str):
        super().__init__(beaker)
        self.webhook_url = webhook_url

    def notify(self, workload: BeakerWorkload, event: Event, job: BeakerJob | None = None) -> None:
        del job  # unused for now

        workload_name = f"{self.beaker.user_name}/{workload.experiment.name}"
        workload_url = self.beaker.workload.url(workload)

        if event == "started":
            text = f":check: Workload <{workload_url}|*{workload_name}*> has started! :runner:"
        elif event == "preempted":
            text = f":warning: Workload <{workload_url}|*{workload_name}*> was preempted!"
        elif event == "failed":
            text = f":check-failed: Workload <{workload_url}|*{workload_name}*> failed!"
        elif event == "succeeded":
            text = f":check: Workload <{workload_url}|*{workload_name}*> succeeded!"
        else:
            raise ValueError(f"Unknown event: {event}")

        requests.post(self.webhook_url, json={"text": text})
