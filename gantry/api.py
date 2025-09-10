"""
Gantry's public API.
"""

import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Literal, Sequence

import rich
from beaker import (
    Beaker,
    BeakerCluster,
    BeakerGroup,
    BeakerJob,
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
from .exceptions import *
from .git_utils import GitRepoState

__all__ = [
    "GitRepoState",
    "launch_experiment",
    "follow_workload",
    "update_workload_description",
    "write_metrics",
]


def launch_experiment(
    args: Sequence[str],
    name: str | None = None,
    description: str | None = None,
    task_name: str = "main",
    workspace: str | None = None,
    group_names: Sequence[str] | None = None,
    clusters: Sequence[str] | None = None,
    gpu_types: Sequence[str] | None = None,
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
    env_vars: Sequence[str] | None = None,
    env_secrets: Sequence[str] | None = None,
    dataset_secrets: Sequence[str] | None = None,
    timeout: int | None = None,
    task_timeout: str | None = None,
    show_logs: bool | None = None,
    allow_dirty: bool = False,
    dry_run: bool = False,
    yes: bool | None = None,
    save_spec: PathOrStr | None = None,
    priority: str | None = None,
    install: str | None = None,
    no_python: bool = False,
    replicas: int | None = None,
    leader_selection: bool = False,
    host_networking: bool = False,
    propagate_failure: bool | None = None,
    propagate_preemption: bool | None = None,
    synchronized_start_timeout: str | None = None,
    mounts: Sequence[str] | None = None,
    weka: str | None = None,
    budget: str | None = None,
    preemptible: bool | None = None,
    retries: int | None = None,
    results: str = constants.RESULTS_DIR,
    runtime_dir: str = constants.RUNTIME_DIR,
    exec_method: Literal["exec", "bash"] = "exec",
    skip_tcpxo_setup: bool = False,
    default_python_version: str = utils.get_local_python_version(),
    pre_setup: str | None = None,
    post_setup: str | None = None,
    slack_webhook_url: str | None = None,
):
    """
    Launch an experiment on Beaker. Same as the ``gantry run`` command.
    """
    if not args:
        raise ConfigurationError(
            "[ARGS]... are required! For example:\n$ gantry run -- python -c 'print(\"Hello, World!\")'"
        )

    if yes is None:
        if os.environ.get("GANTRY_GITHUB_TESTING"):
            yes = True
        else:
            yes = False
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
    with beaker_utils.init_client(workspace=workspace, yes=yes) as beaker:
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

                groups.append(group)

        # Get the entrypoint dataset.
        entrypoint_dataset = beaker_utils.ensure_entrypoint_dataset(beaker)

        # Validate the input datasets.
        datasets_to_use = beaker_utils.ensure_datasets(beaker, *datasets) if datasets else []

        env_vars_to_use = []
        for e in env_vars or []:
            try:
                env_name, val = e.split("=", 1)
            except ValueError:
                if e in os.environ:
                    env_name, val = e, os.environ[e]
                else:
                    raise ConfigurationError(f"Invalid --env option '{e}'")
            env_vars_to_use.append((env_name, val))

        secret_names: set[str] = set()
        env_secrets_to_use = []
        for e in env_secrets or []:
            try:
                env_secret_name, secret = e.split("=", 1)
            except ValueError:
                if e not in os.environ:
                    raise ConfigurationError(f"Invalid --env-secret option '{e}'")

                env_secret_name = e
                env_secret_value = os.environ[e]
                secret = beaker_utils.ensure_secret(beaker, env_secret_name, env_secret_value)

            secret_names.add(env_secret_name)
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
        if not git_config.is_public and "GITHUB_TOKEN" not in secret_names:
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

        if slack_webhook_url is not None and "GANTRY_SLACK_WEBHOOK_URL" not in secret_names:
            slack_webhook_url_secret = beaker_utils.ensure_secret(
                beaker, "GANTRY_SLACK_WEBHOOK_URL", slack_webhook_url
            )
            env_secrets_to_use.append(("GANTRY_SLACK_WEBHOOK_URL", slack_webhook_url_secret))

        # Initialize experiment and task spec.
        spec = beaker_utils.build_experiment_spec(
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
            + f"[b]Commit:[/] [cyan]{git_config.short_ref}[/] {git_config.short_commit_message() or ''} → [blue u]{git_config.ref_url}[/]\n"
            + f"[b]Branch:[/] [cyan]{git_config.branch}[/] → [blue u]{git_config.branch_url}[/]"
        )

        if dry_run:
            utils.print_stdout(info_header)
            utils.print_stdout(
                f"[b]Name:[/] [cyan]{name}[/]\n[b]Experiment spec:[/]",
                spec.to_json(),
                highlight=True,
            )
            return

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

        info_header = (
            f"[b]Experiment:[/] [cyan]{beaker.user_name}/{workload.experiment.name}[/] → [blue u]{beaker.workload.url(workload)}[/]\n"
            + info_header
        )
        utils.print_stdout(info_header)

        # Can return right away if timeout is 0.
        if timeout == 0:
            return

        job: BeakerJob | None = None
        try:
            job = follow_workload(
                beaker,
                workload,
                timeout=timeout,
                show_logs=show_logs,
                slack_webhook_url=slack_webhook_url,
            )
        except (TermInterrupt, BeakerJobTimeoutError) as exc:
            utils.print_stderr(f"[red][bold]{exc.__class__.__name__}:[/] [i]{exc}[/][/]")
            beaker.workload.cancel(workload)
            utils.print_stderr("[yellow]Experiment cancelled.[/]")
            sys.exit(1)
        except KeyboardInterrupt:
            utils.print_stderr("[yellow]Caught keyboard interrupt...[/]")
            if prompt.Confirm.ask("Would you like to cancel the experiment?"):
                beaker.workload.cancel(workload)
                utils.print_stderr(
                    f"[red]Experiment stopped:[/] [blue u]{beaker.workload.url(workload)}[/]"
                )
                return
            else:
                utils.print_stdout(
                    f"See the experiment at [blue u]{beaker.workload.url(workload)}[/]"
                )
                utils.print_stderr(
                    f"[yellow]To cancel the experiment manually, run:\n[i]$ gantry stop {workload.experiment.id}[/][/]"
                )
                sys.exit(1)

        beaker_utils.display_results(
            beaker,
            workload,
            job,
            info_header if show_logs else None,
            slack_webhook_url=slack_webhook_url,
        )


def follow_workload(
    beaker: Beaker,
    workload: BeakerWorkload,
    *,
    task: BeakerTask | None = None,
    timeout: int = 0,
    tail: bool = False,
    show_logs: bool = True,
    slack_webhook_url: str | None = None,
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
            job = beaker_utils.wait_for_job_to_start(
                beaker=beaker,
                job=job,
                start_time=start_time,
                timeout=timeout,
                show_logs=show_logs,
            )

        assert job is not None

        if slack_webhook_url is not None:
            utils.send_slack_message_for_event(
                beaker=beaker,
                webhook_url=slack_webhook_url,
                workload=workload,
                job=job,
                event="started",
            )

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
        if beaker_utils.job_was_preempted(job):
            utils.print_stdout(f"[yellow]Job '{job.id}' preempted.[/] ")
            preempted_job_ids.add(job.id)
            if slack_webhook_url is not None:
                utils.send_slack_message_for_event(
                    beaker=beaker,
                    webhook_url=slack_webhook_url,
                    workload=workload,
                    job=job,
                    event="preempted",
                )
            continue

        return job


_ORIGINAL_WORKLOAD_DESCRIPTIONS: dict[str, str] = {}


def update_workload_description(
    description: str,
    strategy: Literal["append", "prepend", "replace"] = "replace",
    beaker_token: str | None = None,
    client: Beaker | None = None,
) -> str:
    """
    Update the description of the Gantry workload that this process is running in.

    :param description: The description to set or add, depending on the ``strategy``.
    :param strategy: One of "append", "prepend", or "replace" to indicate how the new description
        should be combined with the original description. Defaults to "replace".
    :param beaker_token: An optional Beaker API token to use. If not provided, the
        ``BEAKER_TOKEN`` environment variable will be used if set, or a Beaker config file.
        Alternatively you can provide an existing :class:`~beaker.Beaker` client via the
        ``client`` parameter.
    :param client: An optional existing :class:`~beaker.Beaker` client to use. If not provided,
        a new client will be created using the provided ``beaker_token`` or environment/config.
    """
    global _ORIGINAL_WORKLOAD_DESCRIPTIONS

    if (workload_id := os.environ.get("BEAKER_WORKLOAD_ID")) is None:
        raise RuntimeError(
            "'update_workload_description' can only be called from within a running workload"
        )

    with ExitStack() as stack:
        if client is None:
            beaker: Beaker = stack.enter_context(
                beaker_utils.init_client(
                    ensure_workspace=False, beaker_token=beaker_token, check_for_upgrades=False
                )
            )
        else:
            beaker = client

        workload = beaker.workload.get(workload_id)
        if workload_id not in _ORIGINAL_WORKLOAD_DESCRIPTIONS:
            _ORIGINAL_WORKLOAD_DESCRIPTIONS[workload_id] = (
                workload.experiment.description or ""
            ).strip()

        og_description = _ORIGINAL_WORKLOAD_DESCRIPTIONS[workload_id]

        if strategy == "append":
            description = og_description + " " + description
        elif strategy == "prepend":
            description = description + " " + og_description
        elif strategy != "replace":
            raise ValueError(
                f"'strategy' must be one of 'append', 'prepend', or 'replace', but got '{strategy}'."
            )

        description = description.strip()
        beaker.workload.update(workload, description=description)

    return description


def write_metrics(metrics: dict[str, Any]):
    """
    Write result metrics for the Gantry workload that this process is running in.

    :param metrics: A JSON-serializable dictionary of metrics to write.
    """
    import json

    if os.environ.get("BEAKER_WORKLOAD_ID") is None:
        raise RuntimeError("'write_metrics' can only be called from within a running workload")
    if (results_dir := os.environ.get("RESULTS_DIR")) is None:
        raise RuntimeError("Results directory not set! Can't write metrics.")
    metrics_path = Path(results_dir) / "metrics.json"
    metrics_path.parent.mkdir(exist_ok=True, parents=True)
    with metrics_path.open("w") as f:
        json.dump(metrics, f)
