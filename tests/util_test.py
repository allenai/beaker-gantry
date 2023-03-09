import pytest

from gantry.exceptions import InvalidRemoteError
from gantry.util import parse_git_remote_url


def test_parse_git_remote_url_ssh():
    assert parse_git_remote_url("git@github.com:allenai/beaker-gantry.git") == (
        "allenai",
        "beaker-gantry",
    )


def test_parse_git_remote_url_https():
    assert parse_git_remote_url("https://github.com/allenai/beaker-gantry.git") == (
        "allenai",
        "beaker-gantry",
    )


def test_invalid_git_remote_url():
    with pytest.raises(InvalidRemoteError):
        parse_git_remote_url("git@github.com/allenai/beaker-gantry.git")
