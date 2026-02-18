import pytest

from gantry.exceptions import InvalidRemoteError
from gantry.git_utils import GitRepoState, _parse_git_remote_url


def test_parse_git_remote_url_ssh():
    assert _parse_git_remote_url("git@github.com:allenai/beaker-gantry.git") == (
        "allenai",
        "beaker-gantry",
    )


def test_parse_git_remote_url_https():
    assert _parse_git_remote_url("https://github.com/allenai/beaker-gantry.git") == (
        "allenai",
        "beaker-gantry",
    )


def test_parse_git_remote_url_username_password():
    assert _parse_git_remote_url(
        "https://USERNAME:PASSWORD@github.com/allenai/beaker-gantry.git"
    ) == (
        "allenai",
        "beaker-gantry",
    )


def test_invalid_git_remote_url():
    with pytest.raises(InvalidRemoteError):
        _parse_git_remote_url("git@gthub.com:allenai/beaker-gantry.git")


def test_git_repo_state_from_remote_repo():
    repo_state = GitRepoState.from_remote("https://github.com/allenai/OLMo-core", branch="main")
    assert repo_state.is_in_tree("README.md")
    assert not repo_state.is_in_tree("FOO")
