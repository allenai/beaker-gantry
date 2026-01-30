import logging
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Literal, Sequence, Type

import rich
from beaker import (
    Beaker,
    BeakerCluster,
    BeakerGroup,
    BeakerJob,
    BeakerSortOrder,
    BeakerTask,
    BeakerTaskResources,
    BeakerWorkload,
)
from beaker.exceptions import (
    BeakerExperimentConflict,
    BeakerGroupNotFound,
    BeakerImageNotFound,
    BeakerSecretNotFound,
)
from rich import prompt
from rich.status import Status

from . import beaker_utils, constants, utils
from .aliases import PathOrStr
from .callbacks import Callback
from .exceptions import *
from .git_utils import GitRepoState

log = logging.getLogger(__name__)


def launch_experiment(
    args: Sequence[str],
    name: str | None = None,
    description: str | None = None,
    task_name: str = "main",
    workspace: str | None = None,
    group_names: Sequence[str] | None = None,
    clusters: Sequence[str] | None = None,
    gpu_types: Sequence[str] | None = None,
    interconnect: Literal["ib", "tcpxo"] | None = None,
    tags: Sequence[str] | None = None,
    hostnames: Sequence[str] | None = None,
    beaker_image: str | None = None,
    docker_image: str | None = None,
    cpus: float | None = None,
    gpus: int | None = None,
    memory: str | None = None,
    shared_memory: str | None = None,
    datasets: Sequence[str] | None = None,
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET,
    ref: str | None = None,
    branch: str | None = None,
    conda_file: PathOrStr | None = None,
    conda_env: str | None = None,
    python_manager: Literal["uv", "conda"] | None = None,
    system_python: bool = False,
    uv_venv: str | None = None,
    uv_extras: Sequence[str] | None = None,
    uv_all_extras: bool | None = None,
    uv_torch_backend: str | None = None,
    env_vars: Sequence[str | tuple[str, str]] | None = None,
    env_secrets: Sequence[str | tuple[str, str]] | None = None,
    dataset_secrets: Sequence[str | tuple[str, str]] | None = None,
    mounts: Sequence[str | tuple[str, str]] | None = None,
    weka: Sequence[str | tuple[str, str]] | None = None,
    uploads: Sequence[str | tuple[str, str]] | None = None,
    timeout: int | None = None,
    task_timeout: str | None = None,
    start_timeout: int | None = None,
    inactive_timeout: int | None = None,
    inactive_soft_timeout: int | None = None,
    show_logs: bool | None = None,
    allow_dirty: bool = False,
    dry_run: bool = False,
    yes: bool | None = None,
    save_spec: PathOrStr | None = None,
    priority: str | None = None,
    install: str | None = None,
    no_python: bool = False,
    replicas: int | None = None,
    leader_selection: bool | None = None,
    host_networking: bool | None = None,
    propagate_failure: bool | None = None,
    propagate_preemption: bool | None = None,
    synchronized_start_timeout: str | None = None,
    budget: str | None = None,
    preemptible: bool | None = None,
    retries: int | None = None,
    results: str = constants.RESULTS_DIR,
    runtime_dir: str = constants.RUNTIME_DIR,
    exec_method: Literal["exec", "bash"] = "exec",
    torchrun: bool = False,
    skip_tcpxo_setup: bool = False,
    skip_nccl_setup: bool = False,
    default_python_version: str = utils.get_local_python_version(),
    pre_setup: str | None = None,
    post_setup: str | None = None,
    aws_config_secret: str | None = None,
    aws_credentials_secret: str | None = None,
    google_credentials_secret: str | None = None,
    callbacks: Sequence[Callback] | None = None,
    git_repo: GitRepoState | None = None,
    auto_cancel: bool = False,
    client: Beaker | None = None,
) -> BeakerWorkload | None:
    """
    Launch an experiment on Beaker. Same as the ``gantry run`` command.

    :param cli_mode: Set to ``True`` if this function is being called from a CLI command.
        This mostly affects how certain prompts and messages are displayed.
    """
    if not args:
        if utils.is_cli_mode():
            raise ConfigurationError(
                "[ARGS]... are required! For example:\n  $ gantry run -- python -c 'print(\"Hello, World!\")'"
            )
        else:
            raise ConfigurationError("'args' are required!")

    if torchrun and not gpus:
        raise ConfigurationError(
            f"{utils.fmt_opt('--torchrun')} mode requires {utils.fmt_opt('--gpus')} to be set to a positive integer."
        )

    if replicas is not None:
        if replicas <= 0:
            raise ConfigurationError(
                f"{utils.fmt_opt('--replicas')} must be a positive integer (got {replicas})"
            )
        elif replicas == 1:
            replicas = None

    if yes is None:
        if os.environ.get("GANTRY_GITHUB_TESTING"):
            yes = True
        else:
            yes = False
    if timeout is None:
        timeout = -1 if show_logs else 0
    if show_logs is None:
        show_logs = timeout != 0
    if timeout == 0 and show_logs:
        raise ConfigurationError(
            f"Cannot use {utils.fmt_opt('--show-logs')} with {utils.fmt_opt('--timeout=0')}!"
        )

    task_resources = BeakerTaskResources(
        cpu_count=cpus, gpu_count=gpus, memory=memory, shared_memory=shared_memory
    )

    # Get git information.
    git_repo = git_repo if git_repo is not None else GitRepoState.from_env(ref=ref, branch=branch)

    # Validate repo state.
    if ref is None and not allow_dirty and git_repo.is_dirty:
        raise DirtyRepoError(
            f"You have uncommitted changes! Use {utils.fmt_opt('--allow-dirty')} to force."
        )

    # Initialize Beaker client and validate workspace.
    with ExitStack() as stack:
        if client is None:
            beaker: Beaker = stack.enter_context(
                beaker_utils.init_client(workspace=workspace, yes=yes)
            )
        else:
            beaker = client

        if beaker_image is None and docker_image is None:
            try:
                beaker.image.get(constants.VERSIONED_DEFAULT_IMAGE)
                beaker_image = constants.VERSIONED_DEFAULT_IMAGE
            except BeakerImageNotFound:
                beaker_image = constants.DEFAULT_IMAGE
        elif beaker_image is not None and docker_image is not None:
            raise ConfigurationError(
                f"{utils.fmt_opt('--beaker-image')} and {utils.fmt_opt('--docker-image')} are mutually exclusive."
            )
        elif beaker_image is not None and beaker_image != constants.DEFAULT_IMAGE:
            try:
                beaker_image = beaker.image.get(beaker_image).id
            except BeakerImageNotFound:
                raise ConfigurationError(f"Beaker image '{beaker_image}' not found")

        if budget is None and not beaker.workspace.get().budget_id:
            budget = prompt.Prompt.ask(
                f"[yellow]Missing {utils.fmt_opt('--budget')} option, "
                "see https://beaker-docs.apps.allenai.org/concept/budgets.html for more information.[/]\n"
                "[i]Please enter the budget account to associate with this experiment[/]",
            )

            if not budget:
                raise ConfigurationError("Budget account must be specified!")

        # Maybe resolve or create group.
        groups: list[BeakerGroup] = []
        if group_names:
            for group_name in group_names:
                group = beaker_utils.resolve_group(beaker, group_name)
                if group is None:
                    if "/" in group_name and not group_name.startswith(f"{beaker.user_name}/"):
                        raise BeakerGroupNotFound(group_name)

                    if prompt.Confirm.ask(
                        f"Group [green]{group_name}[/] not found in workspace, would you like to create this group?"
                    ):
                        group_name = group_name.split("/", 1)[-1]
                        group = beaker.group.create(group_name)
                        utils.print_stdout(
                            f"Group created: [blue u]{beaker_utils.group_url(beaker, group)}[/]"
                        )
                    else:
                        utils.print_stderr("[yellow]canceled[/]")
                        sys.exit(1)

                assert group is not None
                groups.append(group)

        # Get the entrypoint dataset.
        entrypoint_dataset = beaker_utils.ensure_entrypoint_dataset(beaker, budget)

        # Validate the input datasets.
        datasets_to_use = beaker_utils.ensure_datasets(beaker, *datasets) if datasets else []

        env_var_names: set[str] = set()
        env_vars_to_use = []
        for e in env_vars or []:
            if isinstance(e, tuple):
                env_name, val = e
            else:
                try:
                    env_name, val = e.split("=", 1)
                except ValueError:
                    if e in os.environ:
                        env_name, val = e, os.environ[e]
                    else:
                        raise ConfigurationError(f"Invalid env var: '{e}'")
            if env_name in env_var_names:
                raise ConfigurationError(f"Duplicate env var name: '{env_name}'")
            env_var_names.add(env_name)
            env_vars_to_use.append((env_name, val))

        secret_names: set[str] = set()
        env_secrets_to_use = []
        for e in env_secrets or []:
            if isinstance(e, tuple):
                env_secret_name, secret = e
            else:
                try:
                    env_secret_name, secret = e.split("=", 1)
                except ValueError:
                    if beaker_utils.secret_exists(beaker, e):
                        env_secret_name = e
                        secret = e
                    elif e in os.environ:
                        env_secret_name = e
                        env_secret_value = os.environ[e]
                        utils.print_stderr(
                            f"[yellow]Taking secret value for '{e}' from environment[/]"
                        )
                        secret = beaker_utils.ensure_secret(
                            beaker, env_secret_name, env_secret_value
                        )
                    else:
                        raise ConfigurationError(f"Invalid env secret: '{e}'")

            if env_secret_name in secret_names:
                raise ConfigurationError(f"Duplicate env secret name: '{env_secret_name}'")
            if env_secret_name in env_var_names:
                raise ConfigurationError(
                    f"Env secret name '{env_secret_name}' conflicts with an env var of the same name"
                )
            secret_names.add(env_secret_name)
            env_secrets_to_use.append((env_secret_name, secret))

        dataset_secrets_to_use = []
        for ds in dataset_secrets or []:
            if isinstance(ds, tuple):
                secret, mount_path = ds
            else:
                try:
                    secret, mount_path = ds.split(":", 1)
                except ValueError:
                    raise ValueError(f"Invalid dataset secret: '{ds}'")
            dataset_secrets_to_use.append((secret, mount_path))

        mounts_to_use = []
        for m in mounts or []:
            if isinstance(m, tuple):
                source, target = m
            else:
                try:
                    source, target = m.split(":", 1)
                except ValueError:
                    raise ValueError(f"Invalid dataset mount: '{m}'")
            mounts_to_use.append((source, target))

        weka_buckets = []
        for m in weka or []:
            if isinstance(m, tuple):
                source, target = m
            else:
                try:
                    source, target = m.split(":", 1)
                except ValueError:
                    raise ValueError(f"Invalid weka mount: '{m}'")
            weka_buckets.append((source, target))

        if weka_buckets and (not tags or "storage:weka" not in tags):
            tags = list(tags or [])
            tags.append("storage:weka")

        uploads_to_use = []
        for f in uploads or []:
            if isinstance(f, tuple):
                source, target = f
            else:
                try:
                    source, target = f.split(":", 1)
                except ValueError:
                    raise ValueError(f"Invalid upload spec: '{f}'")
            uploads_to_use.append((source, target))

        if interconnect is not None:
            tags = list(tags or [])
            tags.append(f"interconnect:{interconnect}")

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
            all_clusters: list[BeakerCluster] = []
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
                all_clusters = beaker_utils.filter_clusters_by_name(beaker, all_clusters, clusters)

            # Maybe filter based on tags.
            if tags:
                all_clusters = beaker_utils.filter_clusters_by_tags(beaker, all_clusters, tags)

            # Filter based on GPU types.
            if gpu_types:
                all_clusters = beaker_utils.filter_clusters_by_gpu_type(
                    beaker, all_clusters, gpu_types
                )

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

        # Get / set the GitHub token secret.
        gh_token_secret_to_use: str | None = None
        if not git_repo.is_public and "GITHUB_TOKEN" not in secret_names:
            try:
                beaker.secret.get(gh_token_secret)
            except BeakerSecretNotFound:
                utils.print_stderr(
                    f"[yellow]GitHub token secret '{gh_token_secret}' not found in workspace.[/]\n"
                    f"You can create a suitable GitHub token by going to https://github.com/settings/tokens/new "
                    f"and generating a token with the '\N{ballot box with check} repo' scope."
                )

                if "GITHUB_TOKEN" in os.environ:
                    gh_token = prompt.Prompt.ask(
                        "[i]Please paste your GitHub token here or press [/]ENTER[i] to use your local [/]GITHUB_TOKEN",
                        password=True,
                        default=os.environ["GITHUB_TOKEN"],
                        show_default=False,
                    )
                else:
                    gh_token = prompt.Prompt.ask(
                        "[i]Please paste your GitHub token here[/]",
                        password=True,
                    )

                if not gh_token:
                    raise ConfigurationError("token cannot be empty!")

                beaker.secret.write(gh_token_secret, gh_token)
                utils.print_stdout(
                    f"GitHub token secret uploaded to workspace as '{gh_token_secret}'.\n"
                    f"If you need to update this secret in the future, use the command:\n"
                    f"[i]$ gantry config set-gh-token[/]"
                )

            gh_token_secret_to_use = gh_token_secret

        if aws_config_secret is not None:
            try:
                beaker.secret.get(aws_config_secret)
            except BeakerSecretNotFound:
                raise ConfigurationError(
                    f"AWS config secret '{aws_config_secret}' not found in workspace"
                )
            env_secrets_to_use.append(("GANTRY_AWS_CONFIG", aws_config_secret))

        if aws_credentials_secret is not None:
            try:
                beaker.secret.get(aws_credentials_secret)
            except BeakerSecretNotFound:
                raise ConfigurationError(
                    f"AWS credentials secret '{aws_credentials_secret}' not found in workspace"
                )
            env_secrets_to_use.append(("GANTRY_AWS_CREDENTIALS", aws_credentials_secret))

        if google_credentials_secret is not None:
            try:
                beaker.secret.get(google_credentials_secret)
            except BeakerSecretNotFound:
                raise ConfigurationError(
                    f"Google Cloud credentials secret '{google_credentials_secret}' not found in workspace"
                )
            env_secrets_to_use.append(("GANTRY_GOOGLE_CREDENTIALS", google_credentials_secret))

        if leader_selection is None:
            if replicas and torchrun and host_networking is not False:
                leader_selection = True
            else:
                leader_selection = False

        if host_networking is None:
            if replicas and leader_selection:
                host_networking = True
            else:
                host_networking = False

        if torchrun and replicas and leader_selection:
            if propagate_failure is None:
                propagate_failure = True
            if propagate_preemption is None and propagate_failure:
                propagate_preemption = True
            if synchronized_start_timeout is None:
                synchronized_start_timeout = "5m"

        # Initialize experiment and task spec.
        spec = beaker_utils.build_experiment_spec(
            beaker,
            task_name=task_name,
            clusters=list(clusters or []),
            task_resources=task_resources,
            arguments=list(args),
            entrypoint_dataset=entrypoint_dataset.id,
            git_repo=git_repo,
            budget=budget,
            group_names=[group.full_name for group in groups],
            description=description,
            beaker_image=beaker_image,
            docker_image=docker_image,
            gh_token_secret=gh_token_secret_to_use,
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
            host_networking=host_networking,
            propagate_failure=propagate_failure,
            propagate_preemption=propagate_preemption,
            synchronized_start_timeout=synchronized_start_timeout,
            task_timeout=task_timeout,
            mounts=mounts_to_use,
            weka_buckets=weka_buckets,
            uploads=uploads_to_use,
            hostnames=None if hostnames is None else list(hostnames),
            preemptible=preemptible,
            retries=retries,
            results=results,
            runtime_dir=runtime_dir,
            exec_method=exec_method,
            torchrun=torchrun,
            skip_nccl_setup=skip_nccl_setup or skip_tcpxo_setup,
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
            utils.print_stdout(f"Experiment spec saved to {save_spec}")

        if not name:
            default_name = utils.unique_name()
            if yes:
                name = default_name
            else:
                name = prompt.Prompt.ask(
                    "[i]What would you like to call this experiment?[/]",
                    default=utils.unique_name(),
                )

        if not name:
            raise ConfigurationError("Experiment name cannot be empty!")

        if dry_run:
            rich.get_console().rule("[b]Dry run[/]")

        if groups:
            groups_str = "\n ❯ ".join(
                [
                    f"[cyan]{group.full_name}[/] → [blue u]{beaker_utils.group_url(beaker, group)}[/]"
                    for group in groups
                ]
            )
        else:
            groups_str = ""

        beaker.workspace.get().name
        info_header = (
            f"[b]Workspace:[/] [cyan]{beaker.workspace.get().name}[/] → [blue u]{beaker.workspace.url()}[/]\n"
            + (("[b]Groups:[/]\n ❯ " + groups_str + "\n") if groups else "")
            + f"[b]Commit:[/] [cyan]{git_repo.short_ref}[/] {git_repo.short_commit_message() or ''} → [blue u]{git_repo.ref_url}[/]\n"
            + f"[b]Branch:[/] [cyan]{git_repo.branch}[/]"
            + (f" → [blue u]{git_repo.branch_url}[/]" if git_repo.branch_url else "")
        )

        if dry_run:
            utils.print_stdout(info_header)
            utils.print_stdout(
                f"[b]Name:[/] [cyan]{name}[/]\n[b]Experiment spec:[/]",
                spec.to_json(),
                highlight=True,
            )
            return None

        # Beaker experiment names have to be unique, so we add a random suffix if needed.
        name_prefix = name
        attempts = 0
        while True:
            try:
                workload = beaker.experiment.create(name=name, spec=spec)
                break
            except BeakerExperimentConflict:
                attempts += 1
                if attempts == 5:
                    utils.print_stderr(
                        f"[yellow]Many experiments with the name '{name_prefix}' already exist. Consider using a different name.[/]"
                    )
                name_suffix = utils.unique_suffix(max_chars=4 if attempts < 5 else 7)
                name = f"{name_prefix}-{name_suffix}"

        try:
            info_header = (
                f"[b]Experiment:[/] [cyan]{beaker.user_name}/{workload.experiment.name}[/] → [blue u]{beaker.workload.url(workload)}[/]\n"
                + info_header
            )
            utils.print_stdout(info_header)

            # Initialize and attach callbacks.
            callbacks = list(callbacks) if callbacks is not None else []
            for callback in callbacks:
                callback.attach(
                    beaker=beaker,
                    git_repo=git_repo,
                    spec=spec,
                    workload=workload,
                )

            # Can return right away if timeout is 0.
            if timeout == 0:
                return workload
        except (TermInterrupt, KeyboardInterrupt) as exc:
            utils.print_stderr(f"[red][bold]{exc.__class__.__name__}:[/] [i]{exc}[/][/]")
            if auto_cancel:
                beaker.workload.cancel(workload)
                utils.print_stderr("[yellow]Experiment cancelled.[/]")

        job = follow_workload(
            beaker,
            workload,
            timeout=timeout if timeout > 0 else None,
            start_timeout=start_timeout,
            inactive_timeout=inactive_timeout,
            inactive_soft_timeout=inactive_soft_timeout,
            show_logs=show_logs,
            auto_cancel=auto_cancel,
            callbacks=callbacks,
        )

        try:
            beaker_utils.display_results(
                beaker,
                workload,
                job,
                info_header=info_header if show_logs else None,
                callbacks=callbacks,
            )
        finally:
            for callback in callbacks or []:
                callback.detach()

        return workload


def follow_workload(
    beaker: Beaker,
    workload: BeakerWorkload,
    *,
    job: BeakerJob | None = None,
    task: BeakerTask | None = None,
    timeout: int | None = None,
    start_timeout: int | None = None,
    inactive_timeout: int | None = None,
    inactive_soft_timeout: int | None = None,
    tail: bool = False,
    show_logs: bool = True,
    auto_cancel: bool = False,
    callbacks: Sequence[Callback] | None = None,
) -> BeakerJob:
    """
    Follow a workload until completion while streaming logs to stdout.

    :param task: A specific task in the workload to follow. Defaults to the first task.
    :param timeout: The number of seconds to wait for the workload to complete. Raises a timeout
        error if it doesn't complete in time.
    :param start_timeout: The number of seconds to wait for the workload to start running.
        Raises a timeout error if it doesn't start in time.
    :param inactive_timeout: The number of seconds to wait for new logs before timing out.
        Raises a timeout error if no new logs are produced in time.
    :param inactive_soft_timeout: The number of seconds to wait for new logs before timing out.
        Issues a warning notification if no new logs are produced in time.
    :param tail: Start tailing the logs if a job is already running. Otherwise shows all logs.
    :param show_logs: Set to ``False`` to avoid streaming the logs.
    :param auto_cancel: Set to ``True`` to automatically cancel the workload on timeout or
        or SIGTERM.

    :returns: The finalized :class:`~beaker.types.BeakerJob` from the task being followed.

    :raises ~gantry.exceptions.BeakerJobTimeoutError: If ``timeout`` is set to a positive number
        and the workload doesn't complete in time.
    """
    console = rich.get_console()
    start_time = time.monotonic()
    preempted_job_ids = set()
    on_start_called = set()
    stopped: Event | None = None
    sentinel = object()
    exceptions_to_cancel_on: tuple[Type[BaseException], ...] = (GantryInterruptWorkload,)
    if auto_cancel:
        exceptions_to_cancel_on = exceptions_to_cancel_on + (TermInterrupt, BeakerJobTimeoutError)

    def get_latest_job() -> BeakerJob | None:
        job = beaker.workload.get_latest_job(workload, task=task)
        if job is not None and job.id not in preempted_job_ids:
            return job
        else:
            return None

    def fill_log_queue(job: BeakerJob, queue: Queue, stopped: Event):
        try:
            for job_log in beaker.job.logs(job, tail_lines=10 if tail else None, follow=True):
                if stopped.is_set():
                    return
                queue.put(job_log)
        except Exception as e:
            queue.put(e)
        finally:
            queue.put(sentinel)

    while True:
        try:
            job = get_latest_job()

            # Wait for job to be created...
            with ExitStack() as stack:
                msg = "[i]waiting on job...[/]"
                status: Status | None = None
                if not os.environ.get("GANTRY_GITHUB_TESTING"):
                    status = stack.enter_context(console.status(msg, spinner="point", speed=0.8))
                else:
                    utils.print_stdout(msg)
                if job is None:
                    while job is None:
                        if (j := get_latest_job()) is not None:
                            job = j
                        elif timeout is not None and (time.monotonic() - start_time) > timeout:
                            raise BeakerJobTimeoutError(
                                "Timed out while waiting for job to be created"
                            )
                        elif (
                            start_timeout is not None
                            and (time.monotonic() - start_time) > start_timeout
                        ):
                            raise BeakerJobTimeoutError(
                                "Timed out while waiting for job to be created"
                            )
                        else:
                            time.sleep(1.0)

                    if status is not None:
                        status.update("[i]waiting for job to launch...[/]")

                assert job is not None

                # Pull events until job is running or fails (whichever happens first)...
                events = set()
                while not (
                    beaker_utils.job_has_finalized(job)
                    or (beaker_utils.job_has_started(job) and show_logs)
                ):
                    for event in beaker.job.list_summarized_events(
                        job, sort_order=BeakerSortOrder.ascending, sort_field="latest_occurrence"
                    ):
                        event_hashable = (event.latest_occurrence.ToSeconds(), event.latest_message)
                        if event_hashable not in events:
                            events.add(event_hashable)
                            utils.print_stdout(f"✓ [i]{event.latest_message}[/]")
                            time.sleep(0.5)

                    if timeout is not None and (time.monotonic() - start_time) > timeout:
                        for callback in callbacks or []:
                            callback.on_timeout(job)
                        if beaker_utils.job_has_started(job):
                            raise BeakerJobTimeoutError(
                                f"Timed out while waiting for job '{job.id}' to finish"
                            )
                        else:
                            raise BeakerJobTimeoutError(
                                f"Timed out while waiting for job '{job.id}' to start"
                            )
                    elif (
                        start_timeout is not None
                        and not beaker_utils.job_has_started(job)
                        and (time.monotonic() - start_time) > start_timeout
                    ):
                        for callback in callbacks or []:
                            callback.on_start_timeout(job)
                        raise BeakerJobTimeoutError(
                            f"Timed out while waiting for job '{job.id}' to start"
                        )
                    else:
                        time.sleep(0.5)
                        job = beaker.job.get(job.id)

            assert job is not None

            if job.id not in on_start_called:
                for callback in callbacks or []:
                    callback.on_start(job)
                on_start_called.add(job.id)

            # Stream logs...
            if show_logs and beaker_utils.job_has_started(job):
                queue: Queue = Queue()
                stopped = Event()

                thread = Thread(target=fill_log_queue, args=(job, queue, stopped), daemon=True)
                thread.start()

                utils.print_stdout()
                rich.get_console().rule("Logs")

                last_event = time.monotonic()
                last_inactive_warning = 0.0
                while True:
                    try:
                        job_log = queue.get(timeout=1.0)
                        last_event = time.monotonic()
                        if job_log is sentinel:
                            break
                        elif isinstance(job_log, Exception):
                            raise job_log
                        else:
                            log_line = job_log.message.decode()
                            log_time = job_log.timestamp.seconds + job_log.timestamp.nanos / 1e9
                            utils.print_stdout(log_line, markup=False)
                            for callback in callbacks or []:
                                callback.on_log(job, log_line, log_time)
                    except Empty:
                        cur_time = time.monotonic()
                        if (
                            inactive_timeout is not None
                            and (cur_time - last_event) > inactive_timeout
                        ):
                            for callback in callbacks or []:
                                callback.on_inactive_timeout(job)
                            raise BeakerJobTimeoutError(
                                f"Timed out while waiting for job '{job.id}' to produce more logs"
                            )

                        if (
                            inactive_soft_timeout is not None
                            and (cur_time - last_event) > inactive_soft_timeout
                            and (cur_time - last_inactive_warning)
                            > max(inactive_soft_timeout, 3600)
                        ):
                            last_inactive_warning = cur_time
                            formatted_duration = utils.format_timedelta(
                                cur_time - last_event,
                                resolution="minutes"
                                if inactive_soft_timeout % 60 == 0
                                else "seconds",
                            )
                            log.warning(
                                f"Job appears to be inactive! No new logs within the past {formatted_duration}."
                            )
                            for callback in callbacks or []:
                                callback.on_inactive_soft_timeout(job)
                        else:
                            for callback in callbacks or []:
                                callback.on_no_new_logs(job)

                    if timeout is not None and (time.monotonic() - start_time) > timeout:
                        for callback in callbacks or []:
                            callback.on_timeout(job)
                        raise BeakerJobTimeoutError(
                            f"Timed out while waiting for job '{job.id}' to finish"
                        )

                utils.print_stdout()
                rich.get_console().rule("End logs")

            # Wait for job to finalize...
            while not beaker_utils.job_has_finalized(job):
                time.sleep(0.5)
                job = beaker.job.get(job.id)

            utils.print_stdout()

            # If job was preempted, we start over...
            if beaker_utils.job_was_preempted(job):
                utils.print_stdout(f"[yellow]Job '{job.id}' preempted.[/] ")
                preempted_job_ids.add(job.id)
                for callback in callbacks or []:
                    callback.on_preemption(job)
                job = None
                continue

            return job
        except exceptions_to_cancel_on as exc:
            utils.print_stderr(f"[red][bold]{exc.__class__.__name__}:[/] [i]{exc}[/][/]")
            beaker.workload.cancel(workload)
            utils.print_stderr("[yellow]Experiment cancelled.[/]")

            for callback in callbacks or []:
                callback.on_cancellation(job)

            if utils.is_cli_mode():
                sys.exit(1)
            else:
                raise
        except KeyboardInterrupt:
            if utils.is_interactive_terminal():
                utils.print_stderr("[yellow]Caught keyboard interrupt...[/]")
                utils.print_stderr(
                    f"You are currently following [blue u]{beaker.workload.url(workload)}[/]"
                )
                action = prompt.Prompt.ask(
                    "Press [red b]c[/] to [red]cancel[/] the workload, "
                    "[green b]r[/] to [green]resume[/] following, "
                    "or [yellow b]q[/] to [yellow]quit[/]",
                    choices=["c", "r", "q"],
                )
                if action == "c":
                    if prompt.Confirm.ask("Are you sure you'd like to cancel the experiment?"):
                        beaker.workload.cancel(workload)
                        utils.print_stderr(
                            f"[red]Experiment stopped:[/] [blue u]{beaker.workload.url(workload)}[/]"
                        )

                        for callback in callbacks or []:
                            callback.on_cancellation(job)

                        if utils.is_cli_mode():
                            sys.exit(0)
                        else:
                            raise
                elif action == "q":
                    utils.print_stdout(
                        f"See the experiment at [blue u]{beaker.workload.url(workload)}[/]"
                    )
                    utils.print_stderr(
                        f"To [yellow b]cancel[/] the workload manually, run:\n\n"
                        f"  $ gantry stop {workload.experiment.id}\n\n"
                        f"To [green b]resume following[/] the workload, run:\n\n"
                        f"  $ gantry follow --tail {workload.experiment.id}\n"
                    )
            else:
                utils.print_stderr("[yellow]Caught SIGINT...[/]")
                if auto_cancel:
                    beaker.workload.cancel(workload)
                    utils.print_stderr("[yellow]Experiment cancelled.[/]")

            if utils.is_cli_mode():
                sys.exit(1)
            else:
                raise
        finally:
            tail = True
            if stopped is not None:
                stopped.set()
                stopped = None
