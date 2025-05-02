import binascii
import json
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, cast

import requests
import rich
from beaker import (
    Beaker,
    BeakerDataset,
    BeakerDatasetFileAlgorithmType,
    BeakerJob,
    BeakerSortOrder,
    BeakerWorkload,
    BeakerWorkloadStatus,
    BeakerWorkloadType,
)
from beaker.exceptions import (
    BeakerDatasetConflict,
    BeakerSecretNotFound,
    BeakerWorkspaceNotSet,
)
from rich import print, prompt
from rich.console import Console

from . import constants
from .exceptions import *
from .version import VERSION

VERSION_CHECK_INTERVAL = 12 * 3600  # 12 hours
DEFAULT_INTERNAL_CONFIG_LOCATION: Optional[Path] = None
try:
    DEFAULT_INTERNAL_CONFIG_LOCATION = Path.home() / ".beaker" / ".beaker-gantry.json"
except RuntimeError:
    # Can't locate home directory.
    pass


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


@dataclass
class InternalConfig:
    version_checked: Optional[float] = None

    @classmethod
    def load(cls) -> Optional["InternalConfig"]:
        path = DEFAULT_INTERNAL_CONFIG_LOCATION
        if path is None:
            return None
        elif path.is_file():
            with open(path, "r") as f:
                return cls(**json.load(f))
        else:
            return cls()

    def save(self):
        path = DEFAULT_INTERNAL_CONFIG_LOCATION
        if path is None:
            return None
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            with open(path, "w") as f:
                json.dump(asdict(self), f)


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


def get_latest_workload(
    beaker: Beaker,
    *,
    author_name: Optional[str] = None,
    workspace_name: Optional[str] = None,
    running: bool = False,
) -> Optional[BeakerWorkload]:
    workspace = beaker.workspace.get(workspace_name)

    workloads = list(
        beaker.workload.list(
            workspace=workspace,
            finalized=not running,
            workload_type=BeakerWorkloadType.experiment,
            sort_order=BeakerSortOrder.descending,
            sort_field="created",
            author=None if author_name is None else beaker.user.get(author_name),
            limit=1,
        )
    )

    if workloads:
        return workloads[0]
    else:
        return None


def follow_workload(
    beaker: Beaker,
    workload: BeakerWorkload,
    timeout: int = 0,
    tail: bool = False,
    show_logs: bool = True,
) -> BeakerJob:
    console = rich.get_console()
    start_time = time.monotonic()

    with console.status("[i]waiting...[/]", spinner="point", speed=0.8) as status:
        # Wait for job to start...
        while (job := beaker.workload.get_latest_job(workload)) is None:
            time.sleep(1.0)

        # Pull events until job is running (or fails)...
        events = set()
        while not job.status.HasField("finalized"):
            if timeout > 0 and (time.monotonic() - start_time) > timeout:
                raise BeakerJobTimeoutError(f"Timed out while waiting for job '{job.id}' to finish")

            job = beaker.job.get(job.id)

            for event in beaker.job.list_summarized_events(
                job, sort_order=BeakerSortOrder.descending, sort_field="latest_occurrence"
            ):
                event_hashable = (event.latest_occurrence.ToSeconds(), event.latest_message)
                if event_hashable not in events:
                    status.update(f"[i]{event.latest_message}[/]")
                    events.add(event_hashable)
                    if show_logs and event.status.lower() == "started":
                        break
            else:
                time.sleep(1.0)
                continue

            break

    if show_logs:
        print()
        rich.get_console().rule("Logs")
        time.sleep(2.0)  # wait a moment to make sure logs are available before experiment finishes
        for job_log in beaker.job.logs(job, tail_lines=10 if tail else None, follow=True):
            console.print(job_log.message.decode(), highlight=False, markup=False)
            if timeout > 0 and (time.monotonic() - start_time) > timeout:
                raise BeakerJobTimeoutError(f"Timed out while waiting for job '{job.id}' to finish")
        print()
        rich.get_console().rule("End logs")
        print()

    # Wait for job to finalize...
    while not job.status.HasField("finalized"):
        time.sleep(0.5)
        job = beaker.job.get(job.id)

    return job


def display_logs(beaker: Beaker, job: BeakerJob, tail_lines: Optional[int] = None) -> BeakerJob:
    console = rich.get_console()
    print()
    rich.get_console().rule("Logs")
    for job_log in beaker.job.logs(job, follow=True, tail_lines=tail_lines):
        console.print(job_log.message.decode(), highlight=False, markup=False)
    print()
    rich.get_console().rule("End logs")
    return beaker.job.get(job.id)


def display_results(beaker: Beaker, workload: BeakerWorkload, job: BeakerJob):
    status = job.status.status
    if status == BeakerWorkloadStatus.succeeded:
        runtime = job.status.exited - job.status.started  # type: ignore
        results_ds = beaker.dataset.get(job.assignment_details.result_dataset_id)

        print(
            f"[b green]\N{check mark}[/] [b cyan]{workload.experiment.name}[/] completed successfully\n"
            f"[b]Experiment:[/] {beaker.workload.url(workload)}\n"
            f"[b]Results:[/] {beaker.dataset.url(results_ds)}\n"
            f"[b]Runtime:[/] {format_timedelta(runtime)}"
        )

        if job.metrics:
            from google.protobuf.json_format import MessageToDict

            print("[b]Metrics:[/]", MessageToDict(job.metrics))
    elif status == BeakerWorkloadStatus.canceled:
        raise ExperimentFailedError(
            f"Job was canceled, see {beaker.workload.url(workload)} for details"
        )
    elif status == BeakerWorkloadStatus.failed:
        raise ExperimentFailedError(
            f"Job failed with exit code {job.status.exit_code}, see {beaker.workload.url(workload)} for details"
        )
    else:
        raise ValueError(f"unexpected workload status '{status}'")


def ensure_repo(allow_dirty: bool = False) -> Tuple[str, str, str, bool]:
    from git.repo import Repo

    repo = Repo(".")

    # Parse account name, repo name, and current commit.
    account, repo_name = parse_git_remote_url(repo.remote().url)
    git_ref = str(repo.commit())

    # Check if repo is dirty (uncommitted changes).
    if repo.is_dirty() and not allow_dirty:
        raise DirtyRepoError("You have uncommitted changes! Use --allow-dirty to force.")

    # Check if repo is public.
    response = requests.get(f"https://github.com/{account}/{repo_name}")
    if response.status_code not in {200, 404}:
        response.raise_for_status()
    is_public = response.status_code == 200

    return account, repo_name, git_ref, is_public


def ref_exists_on_remote(git_ref: str) -> bool:
    from git.cmd import Git

    git = Git(".")

    output = cast(
        str, git.execute(["git", "branch", "-r", "--contains", git_ref], stdout_as_string=True)
    )
    output = output.strip()
    return len(output) > 0


def ensure_entrypoint_dataset(beaker: Beaker) -> BeakerDataset:
    import hashlib
    from importlib.resources import read_binary

    import gantry

    workspace = beaker.workspace.get()

    # Get hash of the local entrypoint source file.
    sha256_hash = hashlib.sha256()
    contents = replace_tags(read_binary(gantry, constants.ENTRYPOINT))
    sha256_hash.update(contents)

    entrypoint_dataset_name = f"gantry-v{VERSION}-{workspace.id}-{sha256_hash.hexdigest()[:6]}"

    def get_dataset() -> Optional[BeakerDataset]:
        matching_datasets = list(
            beaker.dataset.list(
                workspace=workspace, name_or_description=entrypoint_dataset_name, results=False
            )
        )
        if matching_datasets:
            return matching_datasets[0]
        else:
            return None

    # Ensure gantry entrypoint dataset exists.
    gantry_entrypoint_dataset = get_dataset()
    if gantry_entrypoint_dataset is None:
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
        except BeakerDatasetConflict:  # could be in a race with another `gantry` process.
            time.sleep(1.0)
            gantry_entrypoint_dataset = get_dataset()

    if gantry_entrypoint_dataset is None:
        raise RuntimeError(f"Failed to resolve entrypoint dataset '{entrypoint_dataset_name}'")

    # Verify contents.
    ds_files = list(beaker.dataset.list_files(gantry_entrypoint_dataset))
    for retry in range(1, 4):
        ds_files = list(beaker.dataset.list_files(gantry_entrypoint_dataset))
        if len(ds_files) >= 1:
            break
        else:
            time.sleep(1.5**retry)

    if len(ds_files) != 1:
        raise EntrypointChecksumError(
            f"Entrypoint dataset {beaker.dataset.url(gantry_entrypoint_dataset)} is missing the "
            f"required entrypoint file. Please run again."
        )

    if ds_files[0].HasField("digest"):
        digest = ds_files[0].digest
        expected_value = binascii.hexlify(digest.value).decode()
        hasher = BeakerDatasetFileAlgorithmType(digest.algorithm).hasher()
        hasher.update(contents)
        actual_value = binascii.hexlify(hasher.digest()).decode()
        if actual_value != expected_value:
            raise EntrypointChecksumError(
                f"Checksum failed for entrypoint dataset {beaker.dataset.url(gantry_entrypoint_dataset)}\n"
                f"This could be a bug, or it could mean someone has tampered with the dataset.\n"
                f"If you're sure no one has tampered with it, you can delete the dataset from "
                f"the Beaker dashboard and try again.\n"
                f"Actual digest:\n{digest}"
            )

    return gantry_entrypoint_dataset


def ensure_github_token_secret(
    beaker: Beaker, secret_name: str = constants.GITHUB_TOKEN_SECRET
) -> str:
    try:
        beaker.secret.get(secret_name)
    except BeakerSecretNotFound:
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


def check_for_upgrades(force: bool = False):
    config = InternalConfig.load()
    if (
        not force
        and config is not None
        and config.version_checked is not None
        and (time.time() - config.version_checked <= VERSION_CHECK_INTERVAL)
    ):
        return

    import packaging.version
    import requests

    try:
        response = requests.get(
            "https://pypi.org/simple/beaker-gantry",
            headers={"Accept": "application/vnd.pypi.simple.v1+json"},
            timeout=2,
        )
        if response.ok:
            latest_version = packaging.version.parse(response.json()["versions"][-1])
            current_version = packaging.version.parse(VERSION)
            if latest_version > current_version and (
                not latest_version.is_prerelease or current_version.is_prerelease
            ):
                print_stderr(
                    f":warning: [yellow]You're using [b]gantry v{VERSION}[/], "
                    f"but a newer version ([b]v{latest_version}[/]) is available: "
                    f"https://github.com/allenai/beaker-gantry/releases/tag/v{latest_version}[/]\n"
                    f"[yellow i]You can upgrade by running:[/] pip install --upgrade beaker-gantry beaker-py\n",
                )
            if config is not None:
                config.version_checked = time.time()
                config.save()
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        pass


def init_client(
    workspace: Optional[str] = None,
    yes: bool = False,
    ensure_workspace: bool = True,
) -> Beaker:
    beaker = (
        Beaker.from_env() if workspace is None else Beaker.from_env(default_workspace=workspace)
    )

    if ensure_workspace and workspace is None:
        try:
            default_workspace = beaker.workspace.get()
            if not yes and not prompt.Confirm.ask(
                f"Using default workspace [b cyan]{default_workspace.name}[/]. [i]Is that correct?[/]"
            ):
                raise KeyboardInterrupt
        except BeakerWorkspaceNotSet:
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
