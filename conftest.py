import pytest


@pytest.fixture
def run_name() -> str:
    from gantry.common.util import unique_name

    return unique_name()


@pytest.fixture
def workspace_name() -> str:
    return "ai2/gantry-testing"


@pytest.fixture
def public_workspace_name() -> str:
    return "ai2/gantry-testing-public"
