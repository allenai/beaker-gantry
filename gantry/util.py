import tempfile
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple, cast

import requests
import rich
from beaker import (
    Beaker,
    Dataset,
    DatasetConflict,
    DatasetNotFound,
    Digest,
    Experiment,
    Job,
    SecretNotFound,
    WorkspaceNotSet,
)
from rich import print, prompt
from rich.console import Console

from . import constants
from .constants import GITHUB_TOKEN_SECRET
from .exceptions import *
from .version import VERSION

if TYPE_CHECKING:
    from datetime import timedelta


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


def unique_name() -> str:
    import uuid

    import petname

    return cast(str, petname.generate()) + "-" + str(uuid.uuid4())[:7]


def stderr_console() -> Console:
    return Console(stderr=True)


def print_stderr(*args, **kwargs):
    stderr_console().print(*args, **kwargs)


def print_exception(*args, **kwargs):
    stderr_console().print_exception(*args, **kwargs)


def parse_git_remote_url(url: str) -> Tuple[str, str]:
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


def follow_experiment(
    beaker: Beaker, experiment: Experiment, timeout: int = 0, tail: bool = False
) -> Job:
    console = rich.get_console()

    # Wait for job to start...
    job: Optional[Job] = beaker.experiment.tasks(experiment.id)[0].latest_job  # type: ignore
    if job is None:
        print("Waiting for job to launch..", end="")
        while job is None:
            time.sleep(1.0)
            print(".", end="")
            job = beaker.experiment.tasks(experiment.id)[0].latest_job  # type: ignore

    exit_code: Optional[int] = job.status.exit_code

    stream_logs = exit_code is None and not job.is_finalized
    if stream_logs:
        print()
        rich.get_console().rule("Logs")
        for line_bytes in beaker.job.follow(
            job,
            timeout=timeout if timeout > 0 else None,
            include_timestamps=False,
            since=datetime.utcnow() - timedelta(seconds=5) if tail else None,
        ):
            line = line_bytes.decode(errors="ignore")
            if line.endswith("\n"):
                line = line[:-1]
            console.print(line, highlight=False, markup=False)
        rich.get_console().rule("End logs")
        print()

    return job


def display_results(beaker: Beaker, experiment: Experiment, job: Job):
    exit_code = job.status.exit_code
    if exit_code is None:
        raise ExperimentFailedError("Experiment failed")
    elif exit_code > 0:
        raise ExperimentFailedError(f"Experiment exited with non-zero code ({exit_code})")
    assert job.execution is not None
    assert job.status.started is not None
    assert job.status.exited is not None
    result_dataset = None
    if job.result is not None and job.result.beaker is not None:
        result_dataset = job.result.beaker

    print(
        f"[b green]\N{check mark}[/] [b cyan]{experiment.name}[/] completed successfully\n"
        f"[b]Experiment:[/] {beaker.experiment.url(experiment)}\n"
        f"[b]Runtime:[/] {format_timedelta(job.status.exited - job.status.started)}\n"
        f"[b]Results:[/] {None if result_dataset is None else beaker.dataset.url(result_dataset)}"
    )

    metrics = beaker.experiment.metrics(experiment)
    if metrics is not None:
        print("[b]Metrics:[/]", metrics)


def ensure_repo(allow_dirty: bool = False) -> Tuple[str, str, str, bool]:
    from git.repo import Repo

    repo = Repo(".")
    if repo.is_dirty() and not allow_dirty:
        raise DirtyRepoError("You have uncommitted changes! Use --allow-dirty to force.")
    git_ref = str(repo.commit())
    account, repo = parse_git_remote_url(repo.remote().url)
    response = requests.get(f"https://github.com/{account}/{repo}")
    if response.status_code not in {200, 404}:
        response.raise_for_status()
    is_public = response.status_code == 200
    return account, repo, git_ref, is_public


def ensure_entrypoint_dataset(beaker: Beaker) -> Dataset:
    import hashlib
    from importlib.resources import read_binary

    import gantry

    workspace_id = beaker.workspace.get().id

    # Get hash of the local entrypoint source file.
    sha256_hash = hashlib.sha256()
    contents = replace_tags(read_binary(gantry, constants.ENTRYPOINT))
    sha256_hash.update(contents)

    entrypoint_dataset_name = f"gantry-v{VERSION}-{workspace_id}-{sha256_hash.hexdigest()[:6]}"

    # Ensure gantry entrypoint dataset exists.
    gantry_entrypoint_dataset: Dataset
    try:
        gantry_entrypoint_dataset = beaker.dataset.get(entrypoint_dataset_name)
    except DatasetNotFound:
        # Create it.
        print(f"Creating entrypoint dataset '{entrypoint_dataset_name}'")
        try:
            with tempfile.TemporaryDirectory() as tmpdirname:
                tmpdir = Path(tmpdirname)
                entrypoint_path = tmpdir / constants.ENTRYPOINT
                with open(entrypoint_path, "wb") as entrypoint_file:
                    entrypoint_file.write(contents)
                gantry_entrypoint_dataset = beaker.dataset.create(
                    entrypoint_dataset_name, entrypoint_path
                )
        except DatasetConflict:  # could be in a race with another `gantry` process.
            time.sleep(1.0)
            gantry_entrypoint_dataset = beaker.dataset.get(entrypoint_dataset_name)

    # Verify contents.
    err_msg = (
        f"Checksum failed for entrypoint dataset {beaker.dataset.url(gantry_entrypoint_dataset)}\n"
        f"This could be a bug, or it could mean someone has tampered with the dataset.\n"
        f"If you're sure no one has tampered with it, you can delete the dataset from "
        f"the Beaker dashboard and try again."
    )
    ds_files = list(beaker.dataset.ls(gantry_entrypoint_dataset))
    if len(ds_files) != 1:
        raise EntrypointChecksumError(err_msg)
    if ds_files[0].digest != Digest.from_decoded(sha256_hash.digest(), "SHA256"):
        raise EntrypointChecksumError(err_msg)

    return gantry_entrypoint_dataset


def ensure_github_token_secret(
    beaker: Beaker, secret_name: str = constants.GITHUB_TOKEN_SECRET
) -> str:
    try:
        beaker.secret.get(secret_name)
    except SecretNotFound:
        raise GitHubTokenSecretNotFound(
            f"GitHub token secret '{secret_name}' not found in Beaker workspace!\n"
            f"You can create a suitable GitHub token by going to https://github.com/settings/tokens/new "
            f"and generating a token with '\N{ballot box with check} repo' scope.\n"
            f"Then upload your token as a Beaker secret using the Beaker CLI or Python client."
        )
    return secret_name


def format_timedelta(td: "timedelta") -> str:
    def format_value_and_unit(value: int, unit: str) -> str:
        if value == 1:
            return f"{value} {unit}"
        else:
            return f"{value} {unit}s"

    parts = []
    seconds = int(td.total_seconds())
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        parts.append(format_value_and_unit(days, "day"))
    if hours:
        parts.append(format_value_and_unit(hours, "hour"))
    if minutes:
        parts.append(format_value_and_unit(minutes, "minute"))
    if seconds:
        parts.append(format_value_and_unit(seconds, "second"))
    return ", ".join(parts)


def check_for_upgrades():
    import packaging.version
    import requests

    try:
        response = requests.get(
            "https://api.github.com/repos/allenai/beaker-gantry/releases/latest", timeout=1
        )
        if response.ok:
            latest_version = packaging.version.parse(response.json()["tag_name"])
            if latest_version > packaging.version.parse(VERSION):
                print_stderr(
                    f":warning: [yellow]You're using [b]gantry v{VERSION}[/], "
                    f"but a newer version ([b]v{latest_version}[/]) is available: "
                    f"https://github.com/allenai/beaker-gantry/releases/tag/v{latest_version}[/]\n"
                    f"[yellow i]You can upgrade by running:[/] pip install --upgrade beaker-gantry beaker-py\n",
                )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        pass


def ensure_workspace(
    workspace: Optional[str] = None,
    yes: bool = False,
    gh_token_secret: str = GITHUB_TOKEN_SECRET,
    public_repo: bool = False,
) -> Beaker:
    beaker = (
        Beaker.from_env(session=True)
        if workspace is None
        else Beaker.from_env(session=True, default_workspace=workspace)
    )
    try:
        permissions = beaker.workspace.get_permissions()
        if (
            not public_repo
            and permissions.authorizations is not None
            # a default user called "ai2" gets added to every workspace
            and len(permissions.authorizations) > 2
        ):
            print_stderr(
                f"[yellow]Your workspace [b]{beaker.workspace.url()}[/] has multiple contributors! "
                f"Every contributor can view your GitHub personal access token secret ('{gh_token_secret}').[/]"
            )
            if not yes and not prompt.Confirm.ask(
                "[yellow][i]Are you sure you want to use this workspace?[/][/]"
            ):
                raise KeyboardInterrupt
        elif workspace is None:
            default_workspace = beaker.workspace.get()
            if not yes and not prompt.Confirm.ask(
                f"Using default workspace [b cyan]{default_workspace.full_name}[/]. [i]Is that correct?[/]"
            ):
                raise KeyboardInterrupt
    except WorkspaceNotSet:
        raise ConfigurationError(
            "'--workspace' option is required since you don't have a default workspace set"
        )
    return beaker


def replace_tags(contents: bytes) -> bytes:
    tag_start = contents.find(b"${{")
    while tag_start != -1:
        tag_end = contents.find(b"}}") + 2
        tag = contents[tag_start:tag_end]
        constant_name = tag.split(b" ")[1].decode()
        contents = contents.replace(tag, getattr(constants, constant_name).encode())  # type: ignore
        tag_start = contents.find(b"${{", tag_end)
    assert b"${{" not in contents
    return contents
