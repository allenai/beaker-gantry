import binascii
import hashlib
import json
import platform
import tempfile
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import timedelta
from enum import Enum
from fnmatch import fnmatch
from functools import cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, cast

import rich
from beaker import (
    Beaker,
    BeakerCancelationCode,
    BeakerCluster,
    BeakerDataset,
    BeakerDatasetFileAlgorithmType,
    BeakerGpuType,
    BeakerGroup,
    BeakerJob,
    BeakerSortOrder,
    BeakerWorkload,
    BeakerWorkloadStatus,
    BeakerWorkloadType,
    BeakerWorkspace,
)
from beaker.exceptions import BeakerDatasetConflict, BeakerWorkspaceNotSet
from rich import prompt
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


def unique_suffix(max_chars: int = 7) -> str:
    import uuid

    return str(uuid.uuid4())[:max_chars]


def unique_name() -> str:
    import petname

    return cast(str, petname.generate()) + "-" + unique_suffix()


def get_local_python_version() -> str:
    return ".".join(platform.python_version_tuple()[:-1])


@cache
def stderr_console() -> Console:
    return Console(stderr=True)


def print_stderr(*args, **kwargs):
    stderr_console().print(*args, **kwargs, highlight=False)


def print_stdout(*args, highlight: bool = False, markup: bool = True, **kwargs):
    rich.get_console().print(*args, **kwargs, highlight=highlight, markup=markup)


def print_exception(*args, **kwargs):
    stderr_console().print_exception(*args, **kwargs)


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


def display_logs(
    beaker: Beaker, job: BeakerJob, tail_lines: Optional[int] = None, follow: bool = True
) -> BeakerJob:
    print_stdout()
    rich.get_console().rule("Logs")
    for job_log in beaker.job.logs(job, follow=follow, tail_lines=tail_lines):
        print_stdout(job_log.message.decode(), markup=False)
    print_stdout()
    rich.get_console().rule("End logs")
    return beaker.job.get(job.id)


def get_job_status_str(job: BeakerJob):
    status = job.status.status
    canceled_code = job.status.canceled_code
    if status == BeakerWorkloadStatus.canceled:
        if canceled_code == BeakerCancelationCode.sibling_task_failed:
            return "canceled due to sibling task failure"
        else:
            return "canceled"
    elif status == BeakerWorkloadStatus.failed:
        return f"failed with exit code {job.status.exit_code}"
    else:
        return str(BeakerWorkloadStatus(status).name)


def display_results(
    beaker: Beaker,
    workload: BeakerWorkload,
    job: BeakerJob,
    info_header: Optional[str] = None,
):
    status = job.status.status
    if status == BeakerWorkloadStatus.succeeded:
        runtime = job.status.exited - job.status.started  # type: ignore
        results_ds = beaker.dataset.get(job.assignment_details.result_dataset_id)

        print_stdout(
            f"[b green]\N{check mark}[/] [b cyan]{beaker.user_name}/{workload.experiment.name}[/] ({workload.experiment.id}) completed successfully.\n"
        )

        if info_header:
            print_stdout(info_header)

        print_stdout(
            f"[b]Results:[/] [cyan u]{beaker.dataset.url(results_ds)}[/]\n"
            f"[b]Runtime:[/] {format_timedelta(runtime)}"
        )

        if job.metrics:
            from google.protobuf.json_format import MessageToDict

            print_stdout("[b]Metrics:[/]", MessageToDict(job.metrics), highlight=True)
    elif status in (BeakerWorkloadStatus.canceled, BeakerWorkloadStatus.failed):
        if len(list(workload.experiment.tasks)) > 1:
            show_all_jobs(beaker, workload)
            print_stdout()
        raise ExperimentFailedError(
            f"Job {get_job_status_str(job)}, see {beaker.workload.url(workload)} for details"
        )
    else:
        raise ValueError(f"unexpected workload status '{status}'")


def show_all_jobs(beaker: Beaker, workload: BeakerWorkload):
    print_stdout("Tasks:")
    task_name: Optional[str] = None
    for task in workload.experiment.tasks:
        task_name = task.name
        job = beaker.workload.get_latest_job(workload, task=task)
        assert job is not None
        status_str = get_job_status_str(job)
        style = "[white]"
        if job.status.status == BeakerWorkloadStatus.failed:
            style = "[red]"
        elif job.status.status == BeakerWorkloadStatus.canceled:
            style = "[yellow]"
        print_stdout(
            f"❯ {style}'{task_name}'[/] {status_str} - see [cyan u]{beaker.job.url(job)}[/]"
        )

    assert task_name is not None
    print_stdout(
        f"\nYou can show the logs for a particular task by running:\n"
        f"[i][blue]gantry[/] [cyan]logs {workload.experiment.id} --tail=1000 --task={task_name}[/][/]"
    )


def resolve_group(
    beaker: Beaker,
    group_name: str,
    workspace_name: Optional[str] = None,
    fall_back_to_default_workspace: bool = True,
) -> Optional[BeakerGroup]:
    workspace: Optional[BeakerWorkspace] = None
    if workspace_name is not None or fall_back_to_default_workspace:
        workspace = beaker.workspace.get(workspace_name)

    group_owner: Optional[str] = None
    if "/" in group_name:
        group_owner, group_name = group_name.split("/", 1)

    for group in beaker.group.list(workspace=workspace, name_or_description=group_name):
        if group_owner is not None:
            if f"{group_owner}/{group_name}" == group.full_name:
                return group
        elif group_name == group.name:
            return group
    return None


def group_url(beaker: Beaker, group: BeakerGroup) -> str:
    # NOTE: work-around for https://github.com/allenai/beaker-web/issues/1109, short group URLs
    # don't resolve at the moment.
    org_name = beaker.org_name
    workspace_name = beaker.workspace.get(group.workspace_id).name.split("/", 1)[-1]
    return f"{beaker.config.agent_address}/orgs/{org_name}/workspaces/{workspace_name}/groups/{group.id}"


def get_gpu_type(beaker: Beaker, cluster: BeakerCluster) -> str | None:
    nodes = list(beaker.node.list(cluster=cluster, limit=1))
    if nodes:
        try:
            return BeakerGpuType(nodes[0].node_resources.gpu_type).name.replace("_", " ")
        except ValueError:
            return None
    else:
        return None


def filter_clusters_by_name(
    beaker: Beaker, clusters: Iterable[BeakerCluster], patterns: Sequence[str]
) -> List[BeakerCluster]:
    matches = set()
    matches_by_pattern: Dict[str, int] = defaultdict(int)
    final_clusters = []
    for cl in clusters:
        cl_aliases = list(cl.aliases) + [cl.name]
        for pattern in patterns:
            og_pattern = pattern
            if "/" in pattern:
                org, pattern = pattern.split("/", 1)
            else:
                org = beaker.org_name

            if cl.organization_name != org:
                continue

            if "*" in pattern:
                if not any([fnmatch(alias, pattern) for alias in cl_aliases]):
                    continue
            elif not any([alias == pattern for alias in cl_aliases]):
                continue

            matches_by_pattern[og_pattern] += 1
            if cl.id not in matches:
                matches.add(cl.id)
                final_clusters.append(cl)

    for pattern in patterns:
        if matches_by_pattern[pattern] == 0:
            raise ConfigurationError(f"'{pattern}' didn't match any allowed clusters")

    return final_clusters


def filter_clusters_by_tags(
    beaker: Beaker,
    clusters: Iterable[BeakerCluster],
    tags: Sequence[str],
) -> List[BeakerCluster]:
    del beaker
    final_clusters = []
    for cl in clusters:
        cl_tags = set(cl.tags)
        if all([tag in cl_tags for tag in tags]):
            final_clusters.append(cl)
    return final_clusters


def filter_clusters_by_gpu_type(
    beaker: Beaker,
    clusters: Iterable[BeakerCluster],
    gpu_types: Sequence[str],
) -> List[BeakerCluster]:
    final_clusters = []
    for cl in clusters:
        cl_gpu_type = get_gpu_type(beaker, cl)
        if not cl_gpu_type:
            continue
        for pattern in gpu_types:
            if pattern.lower() in cl_gpu_type.lower():
                final_clusters.append(cl)
                break
    return final_clusters


def ensure_entrypoint_dataset(beaker: Beaker) -> BeakerDataset:
    from importlib.resources import read_binary

    import gantry

    workspace = beaker.workspace.get()

    # Get hash of the local entrypoint source file.
    sha256_hash = hashlib.sha256()
    contents = read_binary(gantry, constants.ENTRYPOINT)
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
        print_stdout(f"Creating entrypoint dataset [cyan]{entrypoint_dataset_name}[/]")
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


def maybe_truncate_text(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    else:
        return s[: n - 1] + "…"


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
    beaker_token: Optional[str] = None,
    check_for_upgrades: bool = True,
) -> Beaker:
    Beaker.MAX_RETRIES = 10_000  # effectively retry forever
    Beaker.BACKOFF_MAX = 32

    kwargs = dict()
    if workspace is not None:
        kwargs["default_workspace"] = workspace
    if beaker_token is not None:
        kwargs["user_token"] = beaker_token
    beaker = Beaker.from_env(check_for_upgrades=check_for_upgrades, **kwargs)  # type: ignore[arg-type]

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


def highlight_pattern(s: str, pattern: str) -> str:
    match = s.lower()
    pattern = pattern.lower()
    start_offset = 0
    while (match_start := match.find(pattern, start_offset)) > -1:
        match_str = f"[b green]{pattern.upper()}[/]"
        s = s[:match_start] + match_str + s[match_start + len(pattern) :]
        start_offset = match_start + len(match_str)
        match = s.lower()
    return s


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
