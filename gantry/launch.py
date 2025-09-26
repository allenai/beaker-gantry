import os
import sys
from pathlib import Path
from typing import Literal, Sequence

import rich
from beaker import (
    BeakerCluster,
    BeakerGroup,
    BeakerJob,
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

from . import beaker_utils, constants, utils
from .aliases import PathOrStr
from .exceptions import *
from .git_utils import GitRepoState
from .notifiers import *


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
    leader_selection: bool | None = None,
    host_networking: bool | None = None,
    propagate_failure: bool | None = None,
    propagate_preemption: bool | None = None,
    synchronized_start_timeout: str | None = None,
    weka: Sequence[str | tuple[str, str]] | None = None,
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
    slack_webhook_url: str | None = None,
    aws_config_secret: str | None = None,
    aws_credentials_secret: str | None = None,
    google_credentials_secret: str | None = None,
) -> BeakerWorkload | None:
    """
    Launch an experiment on Beaker. Same as the ``gantry run`` command.

    :param cli_mode: Set to ``True`` if this function is being called from a CLI command.
        This mostly affects how certain prompts and messages are displayed.
    """
    if not args:
        if utils.is_cli_mode():
            raise ConfigurationError(
                "[ARGS]... are required! For example:\n$ gantry run -- python -c 'print(\"Hello, World!\")'"
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

    if beaker_image is None and docker_image is None:
        beaker_image = constants.DEFAULT_IMAGE
    elif (beaker_image is None) == (docker_image is None):
        raise ConfigurationError(
            f"Either {utils.fmt_opt('--beaker-image')} or {utils.fmt_opt('--docker-image')} must be specified, but not both."
        )

    task_resources = BeakerTaskResources(
        cpu_count=cpus, gpu_count=gpus, memory=memory, shared_memory=shared_memory
    )

    # Get git information.
    git_config = GitRepoState.from_env(ref=ref, branch=branch)

    # Validate repo state.
    if ref is None and not allow_dirty and git_config.is_dirty:
        raise DirtyRepoError(
            f"You have uncommitted changes! Use {utils.fmt_opt('--allow-dirty')} to force."
        )

    # Initialize Beaker client and validate workspace.
    with beaker_utils.init_client(workspace=workspace, yes=yes) as beaker:
        if beaker_image is not None and beaker_image != constants.DEFAULT_IMAGE:
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

                groups.append(group)

        # Get the entrypoint dataset.
        entrypoint_dataset = beaker_utils.ensure_entrypoint_dataset(beaker)

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

        if slack_webhook_url is not None and "GANTRY_SLACK_WEBHOOK_URL" not in secret_names:
            if not slack_webhook_url:
                raise ConfigurationError(
                    f"{utils.fmt_opt('--slack-webhook-url')} cannot be an empty string"
                )

            slack_webhook_url_secret = beaker_utils.ensure_secret(
                beaker, "GANTRY_SLACK_WEBHOOK_URL", slack_webhook_url
            )
            env_secrets_to_use.append(("GANTRY_SLACK_WEBHOOK_URL", slack_webhook_url_secret))

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
            host_networking=host_networking,
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

        info_header = (
            f"[b]Experiment:[/] [cyan]{beaker.user_name}/{workload.experiment.name}[/] → [blue u]{beaker.workload.url(workload)}[/]\n"
            + info_header
        )
        utils.print_stdout(info_header)

        # Can return right away if timeout is 0.
        if timeout == 0:
            return workload

        notifiers: list[Notifier] = []
        if slack_webhook_url:
            notifiers.append(SlackNotifier(beaker, slack_webhook_url))

        job: BeakerJob | None = None
        try:
            job = beaker_utils.follow_workload(
                beaker,
                workload,
                timeout=timeout,
                show_logs=show_logs,
                notifiers=notifiers,
            )
        except (TermInterrupt, BeakerJobTimeoutError) as exc:
            utils.print_stderr(f"[red][bold]{exc.__class__.__name__}:[/] [i]{exc}[/][/]")
            beaker.workload.cancel(workload)
            utils.print_stderr("[yellow]Experiment cancelled.[/]")
            if utils.is_cli_mode():
                sys.exit(1)
            else:
                raise
        except KeyboardInterrupt:
            utils.print_stderr("[yellow]Caught keyboard interrupt...[/]")
            if prompt.Confirm.ask("Would you like to cancel the experiment?"):
                beaker.workload.cancel(workload)
                utils.print_stderr(
                    f"[red]Experiment stopped:[/] [blue u]{beaker.workload.url(workload)}[/]"
                )
                if utils.is_cli_mode():
                    return None
                else:
                    raise
            else:
                utils.print_stdout(
                    f"See the experiment at [blue u]{beaker.workload.url(workload)}[/]"
                )
                utils.print_stderr(
                    f"[yellow]To cancel the experiment manually, run:\n[i]$ gantry stop {workload.experiment.id}[/][/]"
                )
                if utils.is_cli_mode():
                    sys.exit(1)
                else:
                    raise

        beaker_utils.display_results(
            beaker,
            workload,
            job,
            info_header if show_logs else None,
            notifiers=notifiers,
        )
        return workload
