import pytest

from gantry.exceptions import InvalidRemoteError
from gantry.util import highlight_pattern, parse_git_remote_url


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


@pytest.mark.parametrize(
    "s, pattern, result",
    [
        ("NVIDIA A100 80GB", "A", "NVIDI[b green]A[/] [b green]A[/]100 80GB"),
        ("NVIDIA A100 80GB", "A100", "NVIDIA [b green]A100[/] 80GB"),
    ],
)
def test_highlight_pattern(s: str, pattern: str, result: str):
    assert highlight_pattern(s, pattern) == result
