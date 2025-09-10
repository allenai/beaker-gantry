from abc import ABCMeta, abstractmethod
from typing import Literal

from beaker import Beaker, BeakerJob, BeakerWorkload

Event = Literal["started", "failed", "preempted", "succeeded"]


class Notifier(metaclass=ABCMeta):
    def __init__(self, beaker: Beaker):
        self.beaker = beaker

    @abstractmethod
    def notify(self, workload: BeakerWorkload, event: Event, job: BeakerJob | None = None) -> None:
        """Send a notification for the given event."""
        pass
