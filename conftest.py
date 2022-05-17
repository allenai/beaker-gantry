import logging
import random
import sys

import pytest
from beaker import Beaker

logger = logging.getLogger(__name__)


def _get_unique_name() -> str:
    from gantry.common.util import unique_name

    return unique_name()


@pytest.fixture
def run_name() -> str:
    return _get_unique_name()


@pytest.fixture
def workspace_name() -> str:
    return "ai2/gantry-testing"


@pytest.fixture
def public_workspace_name() -> str:
    return "ai2/gantry-testing-public"


@pytest.fixture()
def beaker(workspace_name):
    beaker_client = Beaker.from_env(default_workspace=workspace_name, default_org="ai2")
    return beaker_client


def _get_free_cluster(beaker: Beaker) -> str:
    choices = [
        "ai2/general-cirrascale",
        "ai2/allennlp-cirrascale",
        "ai2/aristo-cirrascale",
        "ai2/mosaic-cirrascale",
        "ai2/s2-cirrascale",
    ]
    random.shuffle(choices)
    for cluster in choices:
        utilization = beaker.cluster.utilization(cluster)
        if utilization.queued_jobs == 0:
            logger.info("Found suitable on-prem cluster '%s'", cluster)
            return cluster
    return "ai2/medium-cpu-testing"


@pytest.fixture()
def beaker_cluster_name(beaker: Beaker) -> str:
    return _get_free_cluster(beaker)


if __name__ == "__main__":
    beaker_client = Beaker.from_env()
    assert len(sys.argv) == 2
    fixture = sys.argv[-1]
    if fixture == "run_name":
        print(_get_unique_name())
    elif fixture == "cluster":
        print(_get_free_cluster(beaker_client))
    else:
        raise ValueError(f"Bad fixture argument '{fixture}'")
