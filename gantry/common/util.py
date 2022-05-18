import platform
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

import rich
from beaker import (
    Beaker,
    Dataset,
    DatasetConflict,
    DatasetNotFound,
    Digest,
    ExperimentSpec,
    SecretNotFound,
    TaskResources,
    TaskSpec,
)
from rich import print
from rich.console import Console

from ..exceptions import *
from ..version import VERSION
from . import constants
from .aliases import PathOrStr

if TYPE_CHECKING:
    from datetime import timedelta


def unique_name() -> str:
    import uuid

    import petname

    return petname.generate() + "-" + str(uuid.uuid4())[:7]


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


def display_logs(logs: Iterable[bytes]):
    console = rich.get_console()

    def print_line(line: str):
        # Remove timestamp
        try:
            _, line = line.split("Z ", maxsplit=1)
        except ValueError:
            pass
        console.print(line, highlight=False)

    line_buffer = ""
    for bytes_chunk in logs:
        chunk = line_buffer + bytes_chunk.decode(errors="ignore")
        chunk = chunk.replace("\r", "\n")
        lines = chunk.split("\n")
        if chunk.endswith("\n"):
            line_buffer = ""
        else:
            # Last line line chunk is probably incomplete.
            lines, line_buffer = lines[:-1], lines[-1]
        for line in lines:
            print_line(line)

    if line_buffer:
        print_line(line_buffer)


def ensure_repo(allow_dirty: bool = False) -> Tuple[str, str, str]:
    from git import Repo

    repo = Repo(".")
    if repo.is_dirty() and not allow_dirty:
        raise DirtyRepoError("You have uncommitted changes! Use --allow-dirty to force.")
    git_ref = str(repo.commit())
    account, repo = parse_git_remote_url(repo.remote().url)
    return account, repo, git_ref


def ensure_entrypoint_dataset(beaker: Beaker) -> Dataset:
    import hashlib
    from importlib.resources import read_binary

    import gantry

    workspace_id = beaker.workspace.get().id

    # Get hash of the local entrypoint source file.
    sha256_hash = hashlib.sha256()
    contents = read_binary(gantry, constants.ENTRYPOINT)
    tag_start = contents.find(b"${{")
    while tag_start != -1:
        tag_end = contents.find(b"}}") + 2
        tag = contents[tag_start:tag_end]
        constant_name = tag.split(b" ")[1].decode()
        contents = contents.replace(tag, getattr(constants, constant_name).encode())  # type: ignore
        tag_start = contents.find(b"${{", tag_end)
    assert b"${{" not in contents
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
    if ds_files[0].digest != Digest(sha256_hash.digest()):
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


def ensure_cluster(beaker: Beaker, task_resources: TaskResources, *clusters: str) -> str:
    cluster_to_use: str
    if not clusters:
        raise ConfigurationError("At least one cluster is required")
    elif len(clusters) == 1:
        cluster_to_use = clusters[0]
    else:
        available_clusters = sorted(
            beaker.cluster.filter_available(task_resources, *clusters), key=lambda x: x.queued_jobs
        )
        if available_clusters:
            cluster_to_use = available_clusters[0].cluster.full_name
            print(f"Using cluster '{cluster_to_use}'")
        else:
            cluster_to_use = clusters[0]
            print_stderr(
                f"No clusters currently have enough free resources available. Will use '{cluster_to_use}' anyway."
            )
    return cluster_to_use


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


def build_experiment_spec(
    task_name: str,
    cluster_to_use: str,
    task_resources: TaskResources,
    arguments: List[str],
    entrypoint_dataset: str,
    github_account: str,
    github_repo: str,
    git_ref: str,
    description: Optional[str] = None,
    beaker_image: Optional[str] = None,
    docker_image: Optional[str] = None,
    gh_token_secret: Optional[str] = constants.GITHUB_TOKEN_SECRET,
    conda: Optional[PathOrStr] = None,
    pip: Optional[PathOrStr] = None,
    nfs: Optional[bool] = None,
):
    task_spec = (
        TaskSpec.new(
            task_name,
            cluster_to_use,
            beaker_image=beaker_image,
            docker_image=docker_image,
            result_path=constants.RESULTS_DIR,
            command=["bash", "/gantry/entrypoint.sh"],
            arguments=arguments,
            resources=task_resources,
        )
        .with_env_var(name="GANTRY_VERSION", value=VERSION)
        .with_env_var(name="GITHUB_TOKEN", secret=gh_token_secret)
        .with_env_var(name="GITHUB_REPO", value=f"{github_account}/{github_repo}")
        .with_env_var(name="GIT_REF", value=git_ref)
        .with_dataset("/gantry", beaker=entrypoint_dataset)
    )

    if conda is not None:
        task_spec = task_spec.with_env_var(
            name="CONDA_ENV_FILE",
            value=str(conda),
        )
    elif not Path(constants.CONDA_ENV_FILE).is_file():
        task_spec = task_spec.with_env_var(name="PYTHON_VERSION", value=platform.python_version())

    if pip is not None:
        task_spec = task_spec.with_env_var(
            name="PIP_REQUIREMENTS_FILE",
            value=str(pip),
        )

    if nfs is None:
        if cluster_to_use in constants.NFS_SUPPORTED_CLUSTERS:
            nfs = True

    if nfs:
        task_spec = task_spec.with_dataset(constants.NFS_MOUNT, host_path=constants.NFS_MOUNT)

    return ExperimentSpec(description=description, tasks=[task_spec])


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
                    f"[yellow i]You can upgrade by running:[/] pip install --upgrade beaker-gantry\n",
                )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        pass
