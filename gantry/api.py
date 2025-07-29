"""
Gantry's public API.
"""

import random
import string
import sys
import time
from pathlib import Path
from typing import List, Literal, Optional, Sequence, Tuple, Union

import rich
from beaker import (
    Beaker,
    BeakerCancelationCode,
    BeakerCluster,
    BeakerExperimentSpec,
    BeakerGroup,
    BeakerJob,
    BeakerJobPriority,
    BeakerRetrySpec,
    BeakerSortOrder,
    BeakerTask,
    BeakerTaskResources,
    BeakerTaskSpec,
    BeakerWorkload,
    BeakerWorkloadStatus,
)
from beaker.exceptions import (
    BeakerExperimentConflict,
    BeakerGroupNotFound,
    BeakerImageNotFound,
    BeakerSecretNotFound,
)
from rich import print, prompt
from rich.status import Status

from . import constants, util
from .aliases import PathOrStr
from .exceptions import *
from .git_utils import GitRepoState
from .util import get_local_python_version, print_stderr
from .version import VERSION

__all__ = ["GitRepoState", "launch_experiment", "follow_workload"]


def _wait_for_job_to_start(
    *,
    beaker: Beaker,
    job: BeakerJob,
    status: Status,
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
                status.update(f"[i]{event.latest_message}[/]")
                events.add(event_hashable)
                time.sleep(0.5)

        time.sleep(0.5)
        job = beaker.job.get(job.id)

    return job


def _job_preempted(job: BeakerJob) -> bool:
    return job.status.status == BeakerWorkloadStatus.canceled and job.status.canceled_code in (
        BeakerCancelationCode.system_preemption,
        BeakerCancelationCode.user_preemption,
    )


def _validate_args(args: Sequence[str]):
    if not args:
        raise ConfigurationError(
            "[ARGS]... are required! For example:\n$ gantry run -- python -c 'print(\"Hello, World!\")'"
        )

    try:
        arg_index = sys.argv.index("--")
    except ValueError:
        raise ConfigurationError("[ARGS]... are required and must all come after '--'")

    # NOTE: if a value was accidentally provided to a flag, like '--preemptible false', click will
    # surprisingly add that value to the args. So we do a check here for that situation.
    given_args = sys.argv[arg_index + 1 :]
    invalid_args = args[: -len(given_args)]
    if invalid_args:
        raise ConfigurationError(
            f"Invalid options, found extra arguments before the '--': "
            f"{', '.join([repr(s) for s in invalid_args])}.\n"
            "Hint: you might be trying to pass a value to a FLAG option.\n"
            "Try 'gantry run --help' for help."
        )


def launch_experiment(
    args: Sequence[str],
    name: Optional[str] = None,
    description: Optional[str] = None,
    task_name: str = "main",
    workspace: Optional[str] = None,
    group_names: Optional[Sequence[str]] = None,
    clusters: Optional[Sequence[str]] = None,
    gpu_types: Optional[Sequence[str]] = None,
    tags: Optional[Sequence[str]] = None,
    hostnames: Optional[Sequence[str]] = None,
    beaker_image: Optional[str] = None,
    docker_image: Optional[str] = None,
    cpus: Optional[float] = None,
    gpus: Optional[int] = None,
    memory: Optional[str] = None,
    shared_memory: Optional[str] = None,
    datasets: Optional[Sequence[str]] = None,
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET,
    ref: Optional[str] = None,
    branch: Optional[str] = None,
    conda_file: Optional[PathOrStr] = None,
    conda_env: Optional[str] = None,
    python_manager: Optional[Literal["uv", "conda"]] = None,
    system_python: bool = False,
    uv_venv: Optional[str] = None,
    uv_extras: Optional[Sequence[str]] = None,
    uv_all_extras: Optional[bool] = None,
    uv_torch_backend: Optional[str] = None,
    env_vars: Optional[Sequence[str]] = None,
    env_secrets: Optional[Sequence[str]] = None,
    dataset_secrets: Optional[Sequence[str]] = None,
    timeout: Optional[int] = None,
    task_timeout: Optional[str] = None,
    show_logs: Optional[bool] = None,
    allow_dirty: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    save_spec: Optional[PathOrStr] = None,
    priority: Optional[str] = None,
    install: Optional[str] = None,
    no_python: bool = False,
    replicas: Optional[int] = None,
    leader_selection: bool = False,
    host_networking: bool = False,
    propagate_failure: Optional[bool] = None,
    propagate_preemption: Optional[bool] = None,
    synchronized_start_timeout: Optional[str] = None,
    mounts: Optional[Sequence[str]] = None,
    weka: Optional[str] = None,
    budget: Optional[str] = None,
    preemptible: Optional[bool] = None,
    retries: Optional[int] = None,
    results: str = constants.RESULTS_DIR,
    runtime_dir: str = constants.RUNTIME_DIR,
    exec_method: Literal["exec", "bash"] = "exec",
    skip_tcpxo_setup: bool = False,
    default_python_version: str = get_local_python_version(),
    pre_setup: Optional[str] = None,
    post_setup: Optional[str] = None,
):
    """
    Launch an experiment on Beaker. Same as the ``gantry run`` command.
    """

    _validate_args(args)

    if timeout is None:
        timeout = -1 if show_logs else 0
    if show_logs is None:
        show_logs = timeout != 0

    if beaker_image is None and docker_image is None:
        beaker_image = constants.DEFAULT_IMAGE
    elif (beaker_image is None) == (docker_image is None):
        raise ConfigurationError(
            "Either --beaker-image or --docker-image must be specified, but not both."
        )

    task_resources = BeakerTaskResources(
        cpu_count=cpus, gpu_count=gpus, memory=memory, shared_memory=shared_memory
    )

    # Get git information.
    git_config = GitRepoState.from_env(ref=ref, branch=branch)

    # Validate repo state.
    if ref is None and not allow_dirty and git_config.is_dirty:
        raise DirtyRepoError("You have uncommitted changes! Use --allow-dirty to force.")

    # Initialize Beaker client and validate workspace.
    with util.init_client(workspace=workspace, yes=yes) as beaker:
        if beaker_image is not None and beaker_image != constants.DEFAULT_IMAGE:
            try:
                beaker_image = beaker.image.get(beaker_image).id
            except BeakerImageNotFound:
                raise ConfigurationError(f"Beaker image '{beaker_image}' not found")

        if budget is None and not beaker.workspace.get().budget_id:
            budget = prompt.Prompt.ask(
                "[yellow]Missing '--budget' option, "
                "see https://beaker-docs.apps.allenai.org/concept/budgets.html for more information.[/]\n"
                "[i]Please enter the budget account to associate with this experiment[/]",
            )

            if not budget:
                raise ConfigurationError("Budget account must be specified!")

        # Maybe resolve or create group.
        groups: List[BeakerGroup] = []
        if group_names:
            for group_name in group_names:
                group = util.resolve_group(beaker, group_name)
                if group is None:
                    if "/" in group_name and not group_name.startswith(f"{beaker.user_name}/"):
                        raise BeakerGroupNotFound(group_name)

                    if prompt.Confirm.ask(
                        f"Group [green]{group_name}[/] not found in workspace, would you like to create this group?"
                    ):
                        group_name = group_name.split("/", 1)[-1]
                        group = beaker.group.create(group_name)
                        print(f"Group created: {util.group_url(beaker, group)}")
                    else:
                        print_stderr("[yellow]canceled[/]")
                        sys.exit(1)

                groups.append(group)

        # Get the entrypoint dataset.
        entrypoint_dataset = util.ensure_entrypoint_dataset(beaker)

        # Get / set the GitHub token secret.
        if not git_config.is_public:
            try:
                beaker.secret.get(gh_token_secret)
            except BeakerSecretNotFound:
                print_stderr(
                    f"[yellow]GitHub token secret '{gh_token_secret}' not found in workspace.[/]\n"
                    f"You can create a suitable GitHub token by going to https://github.com/settings/tokens/new "
                    f"and generating a token with the '\N{ballot box with check} repo' scope."
                )
                gh_token = prompt.Prompt.ask(
                    "[i]Please paste your GitHub token here[/]",
                    password=True,
                )
                if not gh_token:
                    raise ConfigurationError("token cannot be empty!")
                beaker.secret.write(gh_token_secret, gh_token)
                print(
                    f"GitHub token secret uploaded to workspace as '{gh_token_secret}'.\n"
                    f"If you need to update this secret in the future, use the command:\n"
                    f"[i]$ gantry config set-gh-token[/]"
                )

            gh_token_secret = util.ensure_github_token_secret(beaker, gh_token_secret)

        # Validate the input datasets.
        datasets_to_use = ensure_datasets(beaker, *datasets) if datasets else []

        env_vars_to_use = []
        for e in env_vars or []:
            try:
                env_name, val = e.split("=", 1)
            except ValueError:
                raise ValueError("Invalid --env option: {e}")
            env_vars_to_use.append((env_name, val))

        env_secrets_to_use = []
        for e in env_secrets or []:
            try:
                env_secret_name, secret = e.split("=", 1)
            except ValueError:
                raise ValueError(f"Invalid --env-secret option: '{e}'")
            env_secrets_to_use.append((env_secret_name, secret))

        dataset_secrets_to_use = []
        for ds in dataset_secrets or []:
            try:
                secret, mount_path = ds.split(":", 1)
            except ValueError:
                raise ValueError(f"Invalid --dataset-secret option: '{ds}'")
            dataset_secrets_to_use.append((secret, mount_path))

        mounts_to_use = []
        for m in mounts or []:
            try:
                source, target = m.split(":", 1)
            except ValueError:
                raise ValueError(f"Invalid --mount option: '{m}'")
            mounts_to_use.append((source, target))

        weka_buckets = []
        for m in weka or []:
            try:
                source, target = m.split(":", 1)
            except ValueError:
                raise ValueError(f"Invalid --weka option: '{m}'")
            weka_buckets.append((source, target))

        if weka_buckets and (not tags or "storage:weka" not in tags):
            tags = list(tags or [])
            tags.append("storage:weka")

        # Validate clusters.
        if clusters or gpu_types or tags:
            constraints = []
            if clusters:
                constraints.append(f'''name matches any of: "{'", "'.join(clusters)}"''')
            if tags:
                constraints.append(f'''has the tag(s): "{'", "'.join(tags)}"''')
            if gpu_types:
                constraints.append(
                    f'''has any one of these GPU types: "{'", "'.join(gpu_types)}"'''
                )

            # Collect all clusters that support batch jobs.
            all_clusters: List[BeakerCluster] = []
            for cl in beaker.cluster.list():
                # If 'max_task_timeout' is set to 0 then tasks are not allowed.
                if cl.HasField("max_task_timeout") and cl.max_task_timeout.ToMilliseconds() == 0:
                    continue
                else:
                    all_clusters.append(cl)

            if not all_clusters:
                raise RuntimeError("Failed to find any clusters that support batch jobs")

            # Maybe filter clusters based on provided patterns.
            if clusters:
                all_clusters = util.filter_clusters_by_name(beaker, all_clusters, clusters)

            # Maybe filter based on tags.
            if tags:
                all_clusters = util.filter_clusters_by_tags(beaker, all_clusters, tags)

            # Filter based on GPU types.
            if gpu_types:
                all_clusters = util.filter_clusters_by_gpu_type(beaker, all_clusters, gpu_types)

            if not all_clusters:
                constraints_str = "\n - ".join(constraints)
                raise ConfigurationError(
                    f"Failed to find clusters satisfying the given constraints:\n - {constraints_str}"
                )
            else:
                clusters = [f"{cl.organization_name}/{cl.name}" for cl in all_clusters]

        # Default to preemptible when no cluster has been specified.
        if not clusters and preemptible is None:
            preemptible = True

        # Initialize experiment and task spec.
        spec = _build_experiment_spec(
            task_name=task_name,
            clusters=list(clusters or []),
            task_resources=task_resources,
            arguments=list(args),
            entrypoint_dataset=entrypoint_dataset.id,
            git_config=git_config,
            budget=budget,
            group_names=[group.full_name for group in groups],
            description=description,
            beaker_image=beaker_image,
            docker_image=docker_image,
            gh_token_secret=gh_token_secret if not git_config.is_public else None,
            conda_file=conda_file,
            conda_env=conda_env,
            python_manager=python_manager,
            system_python=system_python,
            uv_venv=uv_venv,
            uv_extras=uv_extras,
            uv_all_extras=uv_all_extras,
            uv_torch_backend=uv_torch_backend,
            datasets=datasets_to_use,
            env=env_vars_to_use,
            env_secrets=env_secrets_to_use,
            dataset_secrets=dataset_secrets_to_use,
            priority=priority,
            install=install,
            no_python=no_python,
            replicas=replicas,
            leader_selection=leader_selection,
            host_networking=host_networking or (bool(replicas) and leader_selection),
            propagate_failure=propagate_failure,
            propagate_preemption=propagate_preemption,
            synchronized_start_timeout=synchronized_start_timeout,
            task_timeout=task_timeout,
            mounts=mounts_to_use,
            weka_buckets=weka_buckets,
            hostnames=None if hostnames is None else list(hostnames),
            preemptible=preemptible,
            retries=retries,
            results=results,
            runtime_dir=runtime_dir,
            exec_method=exec_method,
            skip_tcpxo_setup=skip_tcpxo_setup,
            default_python_version=default_python_version,
            pre_setup=pre_setup,
            post_setup=post_setup,
        )

        if save_spec:
            if (
                Path(save_spec).is_file()
                and not yes
                and not prompt.Confirm.ask(
                    f"[yellow]The file '{save_spec}' already exists. "
                    f"[i]Are you sure you want to overwrite it?[/][/]"
                )
            ):
                raise KeyboardInterrupt
            spec.to_file(save_spec)
            print(f"Experiment spec saved to {save_spec}")

        if not name:
            default_name = util.unique_name()
            if yes:
                name = default_name
            else:
                name = prompt.Prompt.ask(
                    "[i]What would you like to call this experiment?[/]", default=util.unique_name()
                )

        if not name:
            raise ConfigurationError("Experiment name cannot be empty!")

        if dry_run:
            rich.get_console().rule("[b]Dry run[/]")
            print(
                f"[b]Workspace:[/] {beaker.workspace.url()}\n"
                f"[b]Groups:[/] {', '.join([util.group_url(beaker, group) for group in groups])}\n"
                f"[b]Commit:[/] {git_config.ref_url}\n"
                f"[b]Branch:[/] {git_config.branch_url}\n"
                f"[b]Name:[/] {name}\n"
                f"[b]Experiment spec:[/]",
                spec.to_json(),
            )
            return

        name_prefix = name
        while True:
            try:
                workload = beaker.experiment.create(name=name, spec=spec)
                break
            except BeakerExperimentConflict:
                name = (
                    name_prefix
                    + "-"
                    + random.choice(string.ascii_lowercase)
                    + random.choice(string.ascii_lowercase)
                    + random.choice(string.digits)
                    + random.choice(string.digits)
                )

        print(
            f"Experiment '{beaker.user_name}/{workload.experiment.name}' ({workload.experiment.id}) submitted.\n"
            f"Experiment URL: {beaker.workload.url(workload)}"
        )

        for group in groups:
            print(f"Group '{group.full_name}': {util.group_url(beaker, group)}")

        # Can return right away if timeout is 0.
        if timeout == 0:
            return

        job: Optional[BeakerJob] = None
        try:
            job = follow_workload(beaker, workload, timeout=timeout, show_logs=show_logs)
        except (TermInterrupt, BeakerJobTimeoutError) as exc:
            print_stderr(f"[red][bold]{exc.__class__.__name__}:[/] [i]{exc}[/][/]")
            beaker.workload.cancel(workload)
            print_stderr("[yellow]Experiment cancelled.[/]")
            sys.exit(1)
        except KeyboardInterrupt:
            print_stderr("[yellow]Caught keyboard interrupt...[/]")
            if prompt.Confirm.ask("Would you like to cancel the experiment?"):
                beaker.workload.cancel(workload)
                print_stderr(f"[red]Experiment stopped:[/] {beaker.workload.url(workload)}")
                return
            else:
                print(f"See the experiment at {beaker.workload.url(workload)}")
                print_stderr(
                    f"[yellow]To cancel the experiment manually, run:\n[i]$ gantry stop {workload.experiment.id}[/][/]"
                )
                sys.exit(1)

        util.display_results(beaker, workload, job)


def _build_experiment_spec(
    *,
    task_name: str,
    clusters: List[str],
    task_resources: BeakerTaskResources,
    arguments: List[str],
    entrypoint_dataset: str,
    git_config: GitRepoState,
    budget: Optional[str] = None,
    group_names: Optional[List[str]] = None,
    description: Optional[str] = None,
    beaker_image: Optional[str] = None,
    docker_image: Optional[str] = None,
    gh_token_secret: Optional[str] = constants.GITHUB_TOKEN_SECRET,
    conda_file: Optional[PathOrStr] = None,
    conda_env: Optional[str] = None,
    python_manager: Optional[Literal["uv", "conda"]] = None,
    system_python: bool = False,
    uv_venv: Optional[str] = None,
    uv_extras: Optional[Sequence[str]] = None,
    uv_all_extras: Optional[bool] = None,
    uv_torch_backend: Optional[str] = None,
    datasets: Optional[List[Tuple[str, Optional[str], str]]] = None,
    env: Optional[List[Tuple[str, str]]] = None,
    env_secrets: Optional[List[Tuple[str, str]]] = None,
    dataset_secrets: Optional[List[Tuple[str, str]]] = None,
    priority: Optional[Union[str, BeakerJobPriority]] = None,
    install: Optional[str] = None,
    no_python: bool = False,
    replicas: Optional[int] = None,
    leader_selection: bool = False,
    host_networking: bool = False,
    propagate_failure: Optional[bool] = None,
    propagate_preemption: Optional[bool] = None,
    synchronized_start_timeout: Optional[str] = None,
    task_timeout: Optional[str] = None,
    mounts: Optional[List[Tuple[str, str]]] = None,
    weka_buckets: Optional[List[Tuple[str, str]]] = None,
    hostnames: Optional[List[str]] = None,
    preemptible: Optional[bool] = None,
    retries: Optional[int] = None,
    results: str = constants.RESULTS_DIR,
    runtime_dir: str = constants.RUNTIME_DIR,
    exec_method: Literal["exec", "bash"] = "exec",
    skip_tcpxo_setup: bool = False,
    default_python_version: str = get_local_python_version(),
    pre_setup: Optional[str] = None,
    post_setup: Optional[str] = None,
):
    if exec_method not in ("exec", "bash"):
        raise ConfigurationError(
            f"expected one of 'exec', 'bash' for --exec-method, but got '{exec_method}'."
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

    if git_config.branch is not None:
        task_spec = task_spec.with_env_var(name="GIT_BRANCH", value=git_config.branch)

    if clusters:
        task_spec = task_spec.with_constraint(cluster=clusters)

    if hostnames:
        task_spec = task_spec.with_constraint(hostname=hostnames)

    if gh_token_secret is not None:
        task_spec = task_spec.with_env_var(name="GITHUB_TOKEN", secret=gh_token_secret)

    if skip_tcpxo_setup:
        task_spec = task_spec.with_env_var(name="GANTRY_SKIP_TCPXO_SETUP", value="1")

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
            raise ConfigurationError("other python options can't be used with --no-python")
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
                f"unknown option for --python-manager: '{python_manager}'. Should be either 'uv' or 'conda'."
            )

        task_spec = task_spec.with_env_var(
            name="GANTRY_PYTHON_MANAGER",
            value=python_manager,
        )

        if python_manager == "uv":
            if conda_env is not None or conda_file is not None:
                raise ConfigurationError(
                    "--conda-* options are only relevant when using the conda python manager (--python-manager=conda)."
                )

            if uv_venv is not None:
                if system_python:
                    raise ConfigurationError(
                        "--system-python flag is incompatible with --uv-venv option."
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
                    "--uv-all-extras/--uv-no-extras is mutually exclusive with --uv-extra"
                )

            if uv_all_extras:
                if not has_project_file:
                    raise ConfigurationError(
                        "--uv-all-extras is only valid when you have a pyproject.toml, setup.py, or setup.cfg file."
                    )

                task_spec = task_spec.with_env_var(name="GANTRY_UV_ALL_EXTRAS", value="1")

            if uv_extras:
                if not has_project_file:
                    raise ConfigurationError(
                        "--uv-extra is only valid when you have a pyproject.toml, setup.py, or setup.cfg file."
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
                    "--uv-* options are only relevant when using the uv python manager (--python-manager=uv)."
                )

            if conda_env is not None:
                if system_python:
                    raise ConfigurationError(
                        "--system-python flag is incompatible with --conda-env option."
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


def ensure_datasets(beaker: Beaker, *datasets: str) -> List[Tuple[str, Optional[str], str]]:
    out = []
    for dataset_str in datasets:
        dataset_name: str
        path: str
        sub_path: Optional[str] = None
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


def follow_workload(
    beaker: Beaker,
    workload: BeakerWorkload,
    *,
    task: BeakerTask | None = None,
    timeout: int = 0,
    tail: bool = False,
    show_logs: bool = True,
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
        with console.status("[i]waiting...[/]", spinner="point", speed=0.8) as status:
            # Wait for job to be created...
            job: BeakerJob | None = None
            while job is None:
                if (
                    j := beaker.workload.get_latest_job(workload, task=task)
                ) is not None and j.id not in preempted_job_ids:
                    job = j
                else:
                    time.sleep(1.0)

            # Wait for job to start...
            job = _wait_for_job_to_start(
                beaker=beaker,
                job=job,
                status=status,
                start_time=start_time,
                timeout=timeout,
                show_logs=show_logs,
            )

        # Stream logs...
        if show_logs and job.status.HasField("started"):
            print()
            rich.get_console().rule("Logs")

            for job_log in beaker.job.logs(job, tail_lines=10 if tail else None, follow=True):
                console.print(job_log.message.decode(), highlight=False, markup=False)
                if timeout > 0 and (time.monotonic() - start_time) > timeout:
                    raise BeakerJobTimeoutError(
                        f"Timed out while waiting for job '{job.id}' to finish"
                    )

            print()
            rich.get_console().rule("End logs")
            print()

        # Wait for job to finalize...
        while not job.status.HasField("finalized"):
            time.sleep(0.5)
            job = beaker.job.get(job.id)

        # If job was preempted, we start over...
        if _job_preempted(job):
            print(f"[yellow]Job '{job.id}' preempted.[/] ")
            preempted_job_ids.add(job.id)
            continue

        return job
