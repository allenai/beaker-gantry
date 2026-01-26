from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path
from typing import cast

import requests
from git import InvalidGitRepositoryError
from git.cmd import Git
from git.refs import Head, RemoteReference
from git.repo import Repo

from . import utils
from .aliases import PathOrStr
from .exceptions import *

__all__ = ["GitRepoState"]

log = logging.getLogger(__name__)


def _parse_git_remote_url(url: str) -> tuple[str, str]:
    """
    Parse a git remote URL into a GitHub (account, repo) pair.

    :raises InvalidRemoteError: If the URL can't be parsed correctly.
    """
    if "github.com" not in url:
        raise InvalidRemoteError(f"Remote ('{url}') must point to a GitHub repo")

    try:
        account, repo = url.split("github.com", 1)[-1].strip("/:").split(".git")[0].split("/")
    except ValueError:
        raise InvalidRemoteError(f"Failed to parse GitHub repo path from remote '{url}'")

    return account, repo


@cache
def _resolve_repo() -> Repo:
    try:
        return Repo(".")
    except InvalidGitRepositoryError as e:
        raise GitError("gantry must be run from the ROOT of a valid git repository!") from e


@dataclass
class GitRepoState:
    """
    Represents the state of a local git repository.

    .. tip::
        Use :meth:`from_env()` to instantiate this class.
    """

    repo: str
    """
    The repository name, e.g. ``"allenai/beaker-gantry"``.
    """
    repo_url: str
    """
    The repository URL for cloning, e.g. ``"https://github.com/allenai/beaker-gantry"``.
    """
    ref: str
    """
    The current commit ref/SHA.
    """
    branch: str | None = None
    """
    The current active branch, if any.
    """

    @property
    def is_dirty(self) -> bool:
        """
        If the local repository state is dirty (uncommitted changes).
        """
        repo = _resolve_repo()
        return repo.is_dirty()

    @cached_property
    def is_public(self) -> bool:
        """
        If the repository is public.
        """
        response = requests.get(self.repo_url)
        if response.status_code not in {200, 404}:
            response.raise_for_status()
        return response.status_code == 200

    @property
    def short_ref(self) -> str:
        """
        Short, 7-character version of the current :data:`ref`.
        """
        if len(self.ref) == 40 and self.ref.isalnum():
            return self.ref[:7]
        else:
            return self.ref

    @property
    def ref_url(self) -> str:
        """
        The URL to the current :data:`ref`.
        """
        return f"{self.repo_url}/commit/{self.short_ref}"

    @property
    def branch_url(self) -> str | None:
        """
        The URL to the current active :data:`branch`.
        """
        if self.branch is None:
            return None
        else:
            return f"{self.repo_url}/tree/{self.branch}"

    @cached_property
    def commit_message(self) -> str | None:
        """
        Full commit message.
        """
        repo = _resolve_repo()
        try:
            return str(repo.commit(self.ref).message)
        except Exception:
            return None

    def short_commit_message(self, max_length: int = 50) -> str | None:
        """
        The commit message, truncated to ``max_length`` characters.
        """
        if self.commit_message is None:
            return None
        msg = self.commit_message.split("\n")[0].strip()
        if len(msg) <= max_length:
            return msg
        else:
            return msg[: max_length - 1] + "…"

    def is_in_tree(self, path: PathOrStr) -> bool:
        """
        Check if a file is in the tree.
        """
        try:
            path = Path(path).resolve().relative_to(Path("./").resolve())
        except ValueError:
            return False

        repo = _resolve_repo()
        tree = repo.commit(self.ref).tree
        return str(path) in tree

    @classmethod
    def from_env(cls, ref: str | None = None, branch: str | None = None) -> GitRepoState:
        """
        Instantiate this class from the root of a git repository.

        :raises ~gantry.exceptions.GitError: If this method isn't called from the
            root of a valid git repository.
        :raises ~gantry.exceptions.UnpushedChangesError: If there are unpushed commits.
        :raises ~gantry.exceptions.RemoteBranchNotFoundError: If the local branch is not tracking
            a remote branch.
        """
        repo = _resolve_repo()
        git = Git(".")

        git_ref = ref or str(repo.commit())
        remote = repo.remote()

        branch_name: str | None = branch
        if branch_name is None:
            active_branch: Head | None = None
            try:
                active_branch = repo.active_branch
            except TypeError:
                from .beaker_utils import is_running_in_gantry_batch_job

                msg = (
                    "Repo is in 'detached HEAD' state which will result in cloning the entire repo at runtime.\n"
                    "It's recommended to use gantry from a branch instead."
                )
                if utils.is_cli_mode():
                    utils.print_stderr(f"[yellow]{msg}[/]")
                elif not is_running_in_gantry_batch_job():
                    warnings.warn(msg, UserWarning)

            remote_branch: RemoteReference | None = None
            if active_branch is not None:
                remote_branch = active_branch.tracking_branch()
                if remote_branch is None:
                    raise RemoteBranchNotFoundError(
                        f"Failed to resolve remote tracking branch for local branch '{active_branch.name}'.\n"
                        f"Please make sure your branch exists on the remote, e.g. 'git push --set-upstream {remote.name}'."
                    )

            remote_branches_containing_ref = {
                remote_branch_name.strip()
                for remote_branch_name in cast(
                    str,
                    git.execute(
                        ["git", "branch", "-r", "--contains", git_ref], stdout_as_string=True
                    ),
                )
                .strip()
                .split("\n")
            }

            if remote_branch is not None:
                assert remote_branch.name.startswith(remote_branch.remote_name + "/")
                remote = repo.remote(remote_branch.remote_name)
                branch_name = remote_branch.name.replace(remote_branch.remote_name + "/", "", 1)
                if remote_branch.name not in remote_branches_containing_ref:
                    raise UnpushedChangesError(
                        f"Current git ref '{git_ref}' does not appear to exist on the remote tracking branch '{remote_branch.name}'!\n"
                        "Please push your changes and try again."
                    )
            else:
                if not remote_branches_containing_ref:
                    raise UnpushedChangesError(
                        f"Current git ref '{git_ref}' does not appear to exist on the remote!\n"
                        "Please push your changes and try again."
                    )

        account, repo_name = _parse_git_remote_url(remote.url)

        return cls(
            repo=f"{account}/{repo_name}",
            repo_url=f"https://github.com/{account}/{repo_name}",
            ref=git_ref,
            branch=branch_name,
        )
