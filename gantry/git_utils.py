from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property
from typing import cast

import requests
from git import InvalidGitRepositoryError
from git.cmd import Git
from git.refs import Head, RemoteReference
from git.repo import Repo

from .exceptions import *
from .util import print_stderr

log = logging.getLogger(__name__)


def parse_git_remote_url(url: str) -> tuple[str, str]:
    """
    Parse a git remote URL into a GitHub (account, repo) pair.

    :raises InvalidRemoteError: If the URL can't be parsed correctly.
    """
    try:
        account, repo = (
            url.split("https://github.com/")[-1]
            .split("git@github.com:")[-1]
            .split(".git")[0]
            .split("/")
        )
    except ValueError:
        raise InvalidRemoteError(f"Failed to parse GitHub repo path from remote '{url}'")
    return account, repo


def resolve_repo() -> Repo:
    try:
        return Repo(".")
    except InvalidGitRepositoryError as e:
        raise GitError("gantry must be run from the ROOT of a valid git repository!") from e


@dataclass
class GitConfig:
    repo: str
    repo_url: str
    ref: str
    branch: str | None = None

    @property
    def is_dirty(self) -> bool:
        repo = resolve_repo()
        return repo.is_dirty()

    @cached_property
    def is_public(self) -> bool:
        response = requests.get(self.repo_url)
        if response.status_code not in {200, 404}:
            response.raise_for_status()
        return response.status_code == 200

    @property
    def ref_url(self) -> str:
        return f"{self.repo_url}/commit/{self.ref}"

    @property
    def branch_url(self) -> str | None:
        if self.branch is None:
            return None
        else:
            return f"{self.repo_url}/tree/{self.branch}"

    @classmethod
    def from_env(cls, ref: str | None = None, branch: str | None = None) -> GitConfig:
        repo = resolve_repo()
        git = Git(".")

        git_ref = ref or str(repo.commit())
        remote = repo.remote()

        active_branch: Head | None = None
        if branch is not None:
            active_branch = Head(repo, f"refs/heads/{branch}")
        else:
            try:
                active_branch = repo.active_branch
            except TypeError:
                print_stderr(
                    "[yellow]Repo is in 'detached HEAD' state which will result in cloning the entire repo at runtime.\n"
                    "It's recommended to run gantry from a branch instead.[/]"
                )

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
                git.execute(["git", "branch", "-r", "--contains", git_ref], stdout_as_string=True),
            )
            .strip()
            .split("\n")
        }

        branch_name: str | None = None
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

        account, repo_name = parse_git_remote_url(remote.url)

        return cls(
            repo=f"{account}/{repo_name}",
            repo_url=f"https://github.com/{account}/{repo_name}",
            ref=git_ref,
            branch=branch_name,
        )
