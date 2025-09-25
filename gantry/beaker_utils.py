import binascii
import hashlib
import os
import random
import tempfile
import time
from collections import defaultdict
from contextlib import ExitStack
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Literal, Sequence

import rich
from beaker import *
from beaker.exceptions import *
from rich import prompt
from rich.status import Status

from . import constants, utils
from .aliases import PathOrStr
from .exceptions import *
from .git_utils import GitRepoState
from .notifiers import *
from .version import VERSION


def init_client(
    workspace: str | None = None,
    yes: bool = False,
    ensure_workspace: bool = True,
    beaker_token: str | None = None,
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
                f"{utils.fmt_opt('--workspace')} option is required since you don't have a default workspace set"
            )
    return beaker


def job_was_preempted(job: BeakerJob) -> bool:
    return job.status.status == BeakerWorkloadStatus.canceled and job.status.canceled_code in (
        BeakerCancelationCode.system_preemption,
        BeakerCancelationCode.user_preemption,
    )


def get_latest_workload(
    beaker: Beaker,
    *,
    author_name: str | None = None,
    workspace_name: str | None = None,
    running: bool = False,
) -> BeakerWorkload | None:
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


def get_job(
    beaker: Beaker, wl: BeakerWorkload, task: BeakerTask | None, run: int | None = None
) -> BeakerJob | None:
    if run is None:
        return beaker.workload.get_latest_job(wl, task=task)
    else:
        # NOTE: ascending sort order on creation time is not implemented server-side yet
        jobs = list(reversed(list(beaker.job.list(task=task, sort_field="created"))))
        try:
            return jobs[run - 1]
        except IndexError:
            raise ConfigurationError(f"run number {run} does not exist")


def ensure_datasets(beaker: Beaker, *datasets: str) -> list[tuple[str, str | None, str]]:
    out = []
    for dataset_str in datasets:
        dataset_name: str
        path: str
        sub_path: str | None = None
        if dataset_str.count(":") == 1:
            dataset_name, path = dataset_str.split(":")
        elif dataset_str.count(":") == 2:
            dataset_name, sub_path, path = dataset_str.split(":")
        else:
            raise ValueError(
                f"Bad '--dataset' specification: '{dataset_str}'\n"
                f"Datasets should be in the form of 'dataset-name:/mount/location'"
                f"or 'dataset-name:sub/path:/mount/location'"
            )
        dataset_id = beaker.dataset.get(dataset_name).id
        out.append((dataset_id, sub_path, path))
    return out


def ensure_entrypoint_dataset(beaker: Beaker) -> BeakerDataset:
    from importlib.resources import read_binary

    import gantry

    workspace = beaker.workspace.get()

    # Get hash of the local entrypoint source file.
    sha256_hash = hashlib.sha256()
    contents = read_binary(gantry, constants.ENTRYPOINT)
    sha256_hash.update(contents)

    entrypoint_dataset_name = f"gantry-v{VERSION}-{workspace.id}-{sha256_hash.hexdigest()[:6]}"

    def get_dataset() -> BeakerDataset | None:
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
        utils.print_stdout(f"Creating entrypoint dataset [cyan]{entrypoint_dataset_name}[/]")
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


def secret_exists(beaker: Beaker, name: str) -> bool:
    try:
        beaker.secret.get(name)
        return True
    except BeakerSecretNotFound:
        return False


def ensure_secret(beaker: Beaker, name: str, value: str) -> str:
    if not value:
        raise InvalidSecretError(f"Value for secret '{name}' can't be empty")

    # Create a unique name for this secret based on the env var name and a hash
    # of the value.
    sha256_hash = hashlib.sha256()
    sha256_hash.update(value.encode(errors="ignore"))
    secret = f"{name}_{sha256_hash.hexdigest()[:8]}"
    attempts = 1
    while True:
        try:
            s = beaker.secret.get(secret)
        except BeakerSecretNotFound:
            beaker.secret.write(secret, value)
            break

        if beaker.secret.read(s) == value:
            break

        # It's highly unlikely to get a naming conflict here but we handle it anyway.
        secret = f"{name}_{sha256_hash.hexdigest()[:8]}_{attempts}"
        attempts += 1

    return secret


def resolve_group(
    beaker: Beaker,
    group_name: str,
    workspace_name: str | None = None,
    fall_back_to_default_workspace: bool = True,
) -> BeakerGroup | None:
    workspace: BeakerWorkspace | None = None
    if workspace_name is not None or fall_back_to_default_workspace:
        workspace = beaker.workspace.get(workspace_name)

    group_owner: str | None = None
    if "/" in group_name:
        group_owner, group_name = group_name.split("/", 1)

    for group in beaker.group.list(workspace=workspace, name_or_description=group_name):
        if group_owner is not None:
            if f"{group_owner}/{group_name}" == group.full_name:
                return group
        elif group_name == group.name:
            return group
    return None


def get_job_status_str(job: BeakerJob):
    status = job.status.status
    canceled_code = job.status.canceled_code
    if status == BeakerWorkloadStatus.canceled:
        if canceled_code == BeakerCancelationCode.sibling_task_failed:
            return "canceled due to sibling task failure"
        else:
            return "canceled"
    elif status == BeakerWorkloadStatus.failed:
        if job.status.HasField("exit_code") and job.status.exit_code != 0:
            return f"failed with exit code {job.status.exit_code}"
        else:
            return "failed"
    else:
        return str(BeakerWorkloadStatus(status).name)


def show_all_jobs(beaker: Beaker, workload: BeakerWorkload):
    utils.print_stdout("Tasks:")
    task_name: str | None = None
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
        utils.print_stdout(
            f"❯ {style}'{task_name}'[/] {status_str} - see [cyan u]{beaker.job.url(job)}[/]"
        )

    assert task_name is not None
    utils.print_stdout(
        f"\nYou can show the logs for a particular task by running:\n"
        f"[i][blue]gantry[/] [cyan]logs {workload.experiment.id} --tail=1000 --task={task_name}[/][/]"
    )


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
) -> list[BeakerCluster]:
    matches = set()
    matches_by_pattern: dict[str, int] = defaultdict(int)
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
) -> list[BeakerCluster]:
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
) -> list[BeakerCluster]:
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


def wait_for_job_to_start(
    *,
    beaker: Beaker,
    job: BeakerJob,
    start_time: float,
    timeout: int = 0,
    show_logs: bool = True,
) -> BeakerJob:
    # Pull events until job is running (or fails)...
    events = set()
    while not (job.status.HasField("finalized") or (show_logs and job.status.HasField("started"))):
        if timeout > 0 and (time.monotonic() - start_time) > timeout:
            raise BeakerJobTimeoutError(f"Timed out while waiting for job '{job.id}' to finish")

        for event in beaker.job.list_summarized_events(
            job, sort_order=BeakerSortOrder.descending, sort_field="latest_occurrence"
        ):
            event_hashable = (event.latest_occurrence.ToSeconds(), event.latest_message)
            if event_hashable not in events:
                events.add(event_hashable)
                utils.print_stdout(f"✓ [i]{event.latest_message}[/]")
                time.sleep(0.5)

        time.sleep(0.5)
        job = beaker.job.get(job.id)

    return job


def display_logs(
    beaker: Beaker, job: BeakerJob, tail_lines: int | None = None, follow: bool = True
) -> BeakerJob:
    utils.print_stdout()
    rich.get_console().rule("Logs")
    for job_log in beaker.job.logs(job, follow=follow, tail_lines=tail_lines):
        utils.print_stdout(job_log.message.decode(), markup=False)
    utils.print_stdout()
    rich.get_console().rule("End logs")
    return beaker.job.get(job.id)


def display_results(
    beaker: Beaker,
    workload: BeakerWorkload,
    job: BeakerJob,
    info_header: str | None = None,
    notifiers: list[Notifier] | None = None,
):
    status = job.status.status
    runtime = job.status.exited - job.status.started  # type: ignore
    results_ds = beaker.dataset.get(job.assignment_details.result_dataset_id)

    if status == BeakerWorkloadStatus.succeeded:
        utils.print_stdout(
            f"[b green]\N{check mark}[/] [b cyan]{beaker.user_name}/{workload.experiment.name}[/] ({workload.experiment.id}) completed successfully.\n"
        )

    if info_header:
        utils.print_stdout(info_header)

    utils.print_stdout(
        f"[b]Results:[/] [blue u]{beaker.dataset.url(results_ds)}[/]\n"
        f"[b]Runtime:[/] {utils.format_timedelta(runtime)}"
    )

    if job.metrics:
        from google.protobuf.json_format import MessageToDict

        utils.print_stdout("[b]Metrics:[/]", MessageToDict(job.metrics), highlight=True)

    if status in (BeakerWorkloadStatus.canceled, BeakerWorkloadStatus.failed):
        print()
        if len(list(workload.experiment.tasks)) > 1:
            show_all_jobs(beaker, workload)
            utils.print_stdout()

        for notifier in notifiers or []:
            notifier.notify(workload, "failed", job=job)

        raise ExperimentFailedError(
            f"Job {get_job_status_str(job)}, see {beaker.workload.url(workload)} for details"
        )
    elif status == BeakerWorkloadStatus.succeeded:
        for notifier in notifiers or []:
            notifier.notify(workload, "succeeded", job=job)
    else:
        raise ValueError(f"unexpected workload status '{status}'")


def follow_workload(
    beaker: Beaker,
    workload: BeakerWorkload,
    *,
    task: BeakerTask | None = None,
    timeout: int = 0,
    tail: bool = False,
    show_logs: bool = True,
    notifiers: list[Notifier] | None = None,
) -> BeakerJob:
    """
    Follow a workload until completion while streaming logs to stdout.

    :param task: A specific task in the workload to follow. Defaults to the first task.
    :param timeout: The number of seconds to wait for the workload to complete. Raises a timeout
        error if it doesn't complete in time. Set to 0 (the default) to wait indefinitely.
    :param tail: Start tailing the logs if a job is already running. Otherwise shows all logs.
    :param show_logs: Set to ``False`` to avoid streaming the logs.

    :returns: The finalized :class:`~beaker.types.BeakerJob` from the task being followed.

    :raises ~gantry.exceptions.BeakerJobTimeoutError: If ``timeout`` is set to a positive number
        and the workload doesn't complete in time.
    """
    console = rich.get_console()
    start_time = time.monotonic()
    preempted_job_ids = set()

    while True:
        job: BeakerJob | None = None
        with ExitStack() as stack:
            msg = "[i]waiting on job...[/]"
            status: Status | None = None
            if not os.environ.get("GANTRY_GITHUB_TESTING"):
                status = stack.enter_context(console.status(msg, spinner="point", speed=0.8))
            else:
                utils.print_stdout(msg)

            # Wait for job to be created...
            while job is None:
                if (
                    j := beaker.workload.get_latest_job(workload, task=task)
                ) is not None and j.id not in preempted_job_ids:
                    job = j
                else:
                    time.sleep(1.0)

            if status is not None:
                status.update("[i]waiting for job to launch...[/]")

            # Wait for job to start...
            job = wait_for_job_to_start(
                beaker=beaker,
                job=job,
                start_time=start_time,
                timeout=timeout,
                show_logs=show_logs,
            )

        assert job is not None

        for notifier in notifiers or []:
            notifier.notify(workload, "started", job=job)

        # Stream logs...
        if show_logs and job.status.HasField("started"):
            utils.print_stdout()
            rich.get_console().rule("Logs")

            for job_log in beaker.job.logs(job, tail_lines=10 if tail else None, follow=True):
                utils.print_stdout(job_log.message.decode(), markup=False)
                if timeout > 0 and (time.monotonic() - start_time) > timeout:
                    raise BeakerJobTimeoutError(
                        f"Timed out while waiting for job '{job.id}' to finish"
                    )

            utils.print_stdout()
            rich.get_console().rule("End logs")

        # Wait for job to finalize...
        while not job.status.HasField("finalized"):
            time.sleep(0.5)
            job = beaker.job.get(job.id)

        utils.print_stdout()

        # If job was preempted, we start over...
        if job_was_preempted(job):
            utils.print_stdout(f"[yellow]Job '{job.id}' preempted.[/] ")
            preempted_job_ids.add(job.id)
            for notifier in notifiers or []:
                notifier.notify(workload, "preempted", job=job)
            continue

        return job


def build_experiment_spec(
    *,
    task_name: str,
    clusters: list[str],
    task_resources: BeakerTaskResources,
    arguments: list[str],
    entrypoint_dataset: str,
    git_config: GitRepoState,
    budget: str | None = None,
    group_names: list[str] | None = None,
    description: str | None = None,
    beaker_image: str | None = None,
    docker_image: str | None = None,
    gh_token_secret: str | None = constants.GITHUB_TOKEN_SECRET,
    conda_file: PathOrStr | None = None,
    conda_env: str | None = None,
    python_manager: Literal["uv", "conda"] | None = None,
    system_python: bool = False,
    uv_venv: str | None = None,
    uv_extras: Sequence[str] | None = None,
    uv_all_extras: bool | None = None,
    uv_torch_backend: str | None = None,
    datasets: list[tuple[str, str | None, str]] | None = None,
    env: list[tuple[str, str]] | None = None,
    env_secrets: list[tuple[str, str]] | None = None,
    dataset_secrets: list[tuple[str, str]] | None = None,
    priority: str | BeakerJobPriority | None = None,
    install: str | None = None,
    no_python: bool = False,
    replicas: int | None = None,
    leader_selection: bool = False,
    host_networking: bool = False,
    propagate_failure: bool | None = None,
    propagate_preemption: bool | None = None,
    synchronized_start_timeout: str | None = None,
    task_timeout: str | None = None,
    mounts: list[tuple[str, str]] | None = None,
    weka_buckets: list[tuple[str, str]] | None = None,
    hostnames: list[str] | None = None,
    preemptible: bool | None = None,
    retries: int | None = None,
    results: str = constants.RESULTS_DIR,
    runtime_dir: str = constants.RUNTIME_DIR,
    exec_method: Literal["exec", "bash"] = "exec",
    torchrun: bool = False,
    skip_nccl_setup: bool = False,
    default_python_version: str = utils.get_local_python_version(),
    pre_setup: str | None = None,
    post_setup: str | None = None,
):
    if exec_method not in ("exec", "bash"):
        raise ConfigurationError(
            f"expected one of 'exec' or 'bash' for {utils.fmt_opt('--exec-method')}, but got '{exec_method}'."
        )

    task_spec = (
        BeakerTaskSpec.new(
            task_name,
            beaker_image=beaker_image,
            docker_image=docker_image,
            result_path=results,
            command=["bash", "/gantry/entrypoint.sh"],
            arguments=arguments,
            resources=task_resources,
            priority=priority,
            preemptible=preemptible,
            replicas=replicas,
            leader_selection=leader_selection,
            host_networking=host_networking,
            propagate_failure=propagate_failure,
            propagate_preemption=propagate_preemption,
            synchronized_start_timeout=synchronized_start_timeout,
            timeout=task_timeout,
        )
        .with_env_var(name="GANTRY_VERSION", value=VERSION)
        .with_env_var(name="GITHUB_REPO", value=git_config.repo)
        .with_env_var(name="GIT_REF", value=git_config.ref)
        .with_env_var(name="GANTRY_TASK_NAME", value=task_name)
        .with_env_var(name="RESULTS_DIR", value=results)
        .with_env_var(name="GANTRY_RUNTIME_DIR", value=runtime_dir)
        .with_env_var(name="GANTRY_EXEC_METHOD", value=exec_method)
        .with_dataset("/gantry", beaker=entrypoint_dataset)
    )

    if torchrun:
        task_spec = task_spec.with_env_var(name="GANTRY_USE_TORCHRUN", value="1")
        if replicas and leader_selection:
            task_spec = task_spec.with_env_var(
                name="GANTRY_RDZV_ID", value=str(random.randint(0, 999))
            )
            task_spec = task_spec.with_env_var(
                name="GANTRY_RDZV_PORT", value=str(random.randint(29_000, 29_999))
            )

    if git_config.branch is not None:
        task_spec = task_spec.with_env_var(name="GIT_BRANCH", value=git_config.branch)

    if clusters:
        task_spec = task_spec.with_constraint(cluster=clusters)

    if hostnames:
        task_spec = task_spec.with_constraint(hostname=hostnames)

    if gh_token_secret is not None:
        task_spec = task_spec.with_env_var(name="GITHUB_TOKEN", secret=gh_token_secret)

    if skip_nccl_setup:
        task_spec = task_spec.with_env_var(name="GANTRY_SKIP_NCCL_SETUP", value="1")

    if no_python:
        task_spec = task_spec.with_env_var(name="GANTRY_NO_PYTHON", value="1")

        if (
            python_manager is not None
            or system_python
            or uv_venv is not None
            or uv_all_extras is not None
            or uv_extras
            or uv_torch_backend is not None
            or conda_env is not None
            or conda_file is not None
        ):
            raise ConfigurationError(
                f"other python options can't be used with {utils.fmt_opt('--no-python')}"
            )
    else:
        has_project_file = (
            git_config.is_in_tree("pyproject.toml")
            or git_config.is_in_tree("setup.py")
            or git_config.is_in_tree("setup.cfg")
        )

        task_spec = task_spec.with_env_var(
            name="GANTRY_DEFAULT_PYTHON_VERSION",
            value=default_python_version,
        )

        if system_python:
            task_spec = task_spec.with_env_var(
                name="GANTRY_USE_SYSTEM_PYTHON",
                value="1",
            )

        if python_manager is None:
            if (
                conda_env is not None
                or conda_file is not None
                or git_config.is_in_tree("environment.yml")
                or git_config.is_in_tree("environment.yaml")
            ):
                python_manager = "conda"
            else:
                python_manager = "uv"
        elif python_manager not in {"uv", "conda"}:
            raise ConfigurationError(
                f"unknown option for {utils.fmt_opt('--python-manager')}: '{python_manager}'. Should be either 'uv' or 'conda'."
            )

        task_spec = task_spec.with_env_var(
            name="GANTRY_PYTHON_MANAGER",
            value=python_manager,
        )

        if python_manager == "uv":
            if conda_env is not None or conda_file is not None:
                raise ConfigurationError(
                    f"{utils.fmt_opt('--conda-*')} options are only relevant when using the conda python manager "
                    f"({utils.fmt_opt('--python-manager')}=conda)."
                )

            if uv_venv is not None:
                if system_python:
                    raise ConfigurationError(
                        f"{utils.fmt_opt('--system-python')} flag is incompatible with "
                        f"{utils.fmt_opt('--uv-venv')} option."
                    )

                task_spec = task_spec.with_env_var(
                    name="GANTRY_UV_VENV",
                    value=uv_venv,
                )

            if uv_all_extras is None:
                if not uv_extras and has_project_file:
                    uv_all_extras = True
                else:
                    uv_all_extras = False
            elif uv_extras:
                raise ConfigurationError(
                    f"{utils.fmt_opt('--uv-all-extras/--uv-no-extras')} is mutually exclusive "
                    f"with {utils.fmt_opt('--uv-extra')}."
                )

            if uv_all_extras:
                if not has_project_file:
                    raise ConfigurationError(
                        f"{utils.fmt_opt('--uv-all-extras')} is only valid when you have a pyproject.toml, setup.py, or setup.cfg file."
                    )

                task_spec = task_spec.with_env_var(name="GANTRY_UV_ALL_EXTRAS", value="1")

            if uv_extras:
                if not has_project_file:
                    raise ConfigurationError(
                        f"{utils.fmt_opt('--uv-extra')} is only valid when you have a pyproject.toml, setup.py, or setup.cfg file."
                    )

                task_spec = task_spec.with_env_var(
                    name="GANTRY_UV_EXTRAS", value=" ".join(uv_extras)
                )

            if uv_torch_backend is not None:
                task_spec = task_spec.with_env_var(name="UV_TORCH_BACKEND", value=uv_torch_backend)
        elif python_manager == "conda":
            if (
                uv_venv is not None
                or uv_extras
                or uv_all_extras is not None
                or uv_torch_backend is not None
            ):
                raise ConfigurationError(
                    f"{utils.fmt_opt('--uv-*')} options are only relevant when using the uv python "
                    f"manager ({utils.fmt_opt('--python-manager')}=uv)."
                )

            if conda_env is not None:
                if system_python:
                    raise ConfigurationError(
                        f"{utils.fmt_opt('--system-python')} flag is incompatible with "
                        f"{utils.fmt_opt('--conda-env')} option."
                    )

                task_spec = task_spec.with_env_var(
                    name="GANTRY_CONDA_ENV",
                    value=conda_env,
                )

            if conda_file is not None:
                task_spec = task_spec.with_env_var(
                    name="GANTRY_CONDA_FILE",
                    value=str(conda_file),
                )
            else:
                for path in ("environment.yml", "environment.yaml"):
                    if git_config.is_in_tree(path):
                        task_spec = task_spec.with_env_var(
                            name="GANTRY_CONDA_FILE",
                            value=path,
                        )
                        break

    if install is not None:
        task_spec = task_spec.with_env_var(name="GANTRY_INSTALL_CMD", value=install)

    if pre_setup is not None:
        task_spec = task_spec.with_env_var(name="GANTRY_PRE_SETUP_CMD", value=pre_setup)

    if post_setup is not None:
        task_spec = task_spec.with_env_var(name="GANTRY_POST_SETUP_CMD", value=post_setup)

    if datasets:
        for dataset_id, sub_path, path in datasets:
            task_spec = task_spec.with_dataset(path, beaker=dataset_id, sub_path=sub_path)

    for secret, mount_path in dataset_secrets or []:
        task_spec = task_spec.with_dataset(mount_path, secret=secret)

    if mounts:
        for source, target in mounts:
            task_spec = task_spec.with_dataset(target, host_path=source)

    if weka_buckets:
        for source, target in weka_buckets:
            task_spec = task_spec.with_dataset(target, weka=source)

    for name, val in env or []:
        task_spec = task_spec.with_env_var(name=name, value=val)

    for name, secret in env_secrets or []:
        task_spec = task_spec.with_env_var(name=name, secret=secret)

    return BeakerExperimentSpec(
        description=description,
        budget=budget,
        tasks=[task_spec],
        groups=group_names,
        retry=None if not retries else BeakerRetrySpec(allowed_task_retries=retries),
    )
