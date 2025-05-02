import logging

import pytest
from beaker import Beaker

logger = logging.getLogger(__name__)


def _get_unique_name() -> str:
    from gantry.util import unique_name

    return unique_name()


@pytest.fixture
def run_name() -> str:
    return _get_unique_name()


@pytest.fixture(scope="session")
def workspace_name() -> str:
    return "ai2/gantry-testing"


@pytest.fixture(scope="session")
def cluster_name() -> str:
    return "ai2/jupiter-cirrascale-2"


@pytest.fixture(scope="session")
def beaker(workspace_name: str):
    with Beaker.from_env(default_workspace=workspace_name, default_org="ai2") as client:
        yield client


@pytest.fixture(scope="session")
def user_name(beaker: Beaker) -> str:
    return beaker.user_name
