import dataclasses
from dataclasses import dataclass

import beaker.beaker_pb2 as pb2
from beaker import Beaker, BeakerJob

import gantry.beaker_utils as beaker_utils


@dataclass
class JobStatus:
    job: BeakerJob = dataclasses.field(init=True, repr=False)
    events: list[pb2.SummarizedJobEvent]

    @property
    def id(self) -> str:
        return self.job.id

    @property
    def latest_event(self) -> pb2.SummarizedJobEvent | None:
        if not self.events:
            return None
        return sorted(self.events, key=lambda event: event.latest_occurrence.ToSeconds())[-1]

    @property
    def has_started(self) -> bool:
        return beaker_utils.job_has_started(self.job)

    @property
    def was_preempted(self) -> bool:
        return beaker_utils.job_was_preempted(self.job)

    @property
    def has_finalized(self) -> bool:
        return beaker_utils.job_has_finalized(self.job)
