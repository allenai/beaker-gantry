import logging
import sys

import pytest
from beaker import Beaker

logger = logging.getLogger(__name__)


def _get_unique_name() -> str:
    from gantry.util import unique_name

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


if __name__ == "__main__":
    beaker_client = Beaker.from_env()
    assert len(sys.argv) == 2
    fixture = sys.argv[-1]
    if fixture == "run_name":
        print(_get_unique_name())
    else:
        raise ValueError(f"Bad fixture argument '{fixture}'")
