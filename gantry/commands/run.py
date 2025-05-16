import platform
import random
import string
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional, Tuple, Union

import click
import rich
from beaker import (
    Beaker,
    BeakerExperimentSpec,
    BeakerGroup,
    BeakerJob,
    BeakerJobPriority,
    BeakerRetrySpec,
    BeakerTaskResources,
    BeakerTaskSpec,
)
from beaker.exceptions import (
    BeakerExperimentConflict,
    BeakerImageNotFound,
    BeakerSecretNotFound,
)
from click_option_group import optgroup
from rich import print, prompt

from .. import constants, util
from ..aliases import PathOrStr
from ..exceptions import *
from ..git_utils import GitConfig
from ..util import print_stderr
from ..version import VERSION
from .main import CLICK_COMMAND_DEFAULTS, main, new_optgroup


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.help_option("--help", help="Show this message and exit.")
@click.argument("arg", nargs=-1)
@new_optgroup("Bookkeeping")
@optgroup.option(
    "-n",
    "--name",
    type=str,
    help="""A name to assign to the experiment on Beaker. Defaults to a randomly generated name.""",
)
@optgroup.option("-d", "--description", type=str, help="""A description for the experiment.""")
@optgroup.option(
    "-w",
    "--workspace",
    type=str,
    help="""The Beaker workspace to use.
    If not specified, your default workspace will be used.""",
)
@optgroup.option(
    "-b", "--budget", type=str, help="""The budget account to associate with the experiment."""
)
@optgroup.option("--group", "group_name", type=str, help="""A group to assign the experiment to.""")
@new_optgroup("Launch settings")
@optgroup.option(
    "--show-logs/--no-logs",
    default=True,
    show_default=True,
    help="""Whether or not to stream the logs to stdout as the experiment runs.
    This only takes effect when --timeout is non-zero.""",
)
@optgroup.option(
    "--timeout",
    type=int,
    default=0,
    help="""Time to wait (in seconds) for the experiment to finish.
    A timeout of -1 means wait indefinitely.
    A timeout of 0 means don't wait at all.""",
    show_default=True,
)
@optgroup.option(
    "--allow-dirty",
    is_flag=True,
    help="""Allow submitting the experiment with a dirty working directory.""",
)
@optgroup.option(
    "-y",
    "--yes",
    is_flag=True,
    help="""Skip all confirmation prompts.""",
)
@optgroup.option("--dry-run", is_flag=True, help="""Do a dry run only.""")
@optgroup.option(
    "--save-spec",
    type=click.Path(dir_okay=False, file_okay=True),
    help="""A path to save the generated YAML Beaker experiment spec to.""",
)
@new_optgroup("Constraints")
@optgroup.option(
    "-c",
    "--cluster",
    type=str,
    multiple=True,
    default=None,
    help="""A potential cluster to use. This option can be used multiple times to allow multiple clusters.
    You also specify it as a wildcard, e.g. '--cluster ai2/*-cirrascale'.
    If you don't specify a cluster or the priority, the priority will default to 'preemptible' and
    the job will be able to run on any on-premise cluster.""",
    show_default=True,
)
@optgroup.option(
    "--hostname",
    type=str,
    multiple=True,
    default=None,
    help="""Hostname constraints to apply to the experiment spec. This option can be used multiple times to allow
    multiple hosts.""",
    show_default=True,
)
@new_optgroup("Resources")
@optgroup.option(
    "--cpus",
    type=float,
    help="""Minimum number of logical CPU cores (e.g. 4.0, 0.5).""",
)
@optgroup.option(
    "--gpus",
    type=int,
    help="""Minimum number of GPUs (e.g. 1).""",
)
@optgroup.option(
    "--memory",
    type=str,
    help="""Minimum available system memory as a number with unit suffix (e.g. 2.5GiB).""",
)
@optgroup.option(
    "--shared-memory",
    type=str,
    help="""Size of /dev/shm as a number with unit suffix (e.g. 2.5GiB).""",
)
@new_optgroup("Inputs")
@optgroup.option(
    "--beaker-image",
    type=str,
    help=f"""The name or ID of an image on Beaker to use for your experiment.
    Mutually exclusive with --docker-image. Defaults to '{constants.DEFAULT_IMAGE}' if neither is set.""",
)
@optgroup.option(
    "--docker-image",
    type=str,
    help="""The name of a public Docker image to use for your experiment.
    Mutually exclusive with --beaker-image.""",
)
@optgroup.option(
    "--dataset",
    type=str,
    multiple=True,
    help="""An input dataset in the form of 'dataset-name:/mount/location' or
    'dataset-name:sub/path:/mount/location' to attach to your experiment.
    You can specify this option more than once to attach multiple datasets.""",
)
@optgroup.option(
    "-m",
    "--mount",
    type=str,
    help="""Host directories to mount to the Beaker experiment. Should be in the form '{HOST_SOURCE}:{TARGET}'
    similar to the '-v' option with 'docker run'.""",
    multiple=True,
)
@optgroup.option(
    "--weka",
    type=str,
    multiple=True,
    help="""A weka bucket to mount in the form of 'bucket-name:/mount/location',
    e.g. --weka=oe-training-default:/data""",
)
@optgroup.option(
    "--env",
    type=str,
    help="""Environment variables to add the Beaker experiment. Should be in the form '{NAME}={VALUE}'.""",
    multiple=True,
)
@optgroup.option(
    "--env-secret",
    "--secret-env",
    type=str,
    help="""Environment variables to add the Beaker experiment from Beaker secrets.
    Should be in the form '{NAME}={SECRET_NAME}'.""",
    multiple=True,
)
@optgroup.option(
    "--dataset-secret",
    type=str,
    help="""Mount a Beaker secret to a file as a dataset.
    Should be in the form '{SECRET_NAME}:{MOUNT_PATH}'.""",
    multiple=True,
)
@optgroup.option(
    "--ref",
    type=str,
    help="""The target git ref to use. Defaults to the latest commit.""",
)
@optgroup.option(
    "--branch",
    type=str,
    help="""The target git branch to use. Defaults to the active branch.""",
)
@optgroup.option(
    "--gh-token-secret",
    type=str,
    help="""The name of the Beaker secret that contains your GitHub token.""",
    default=constants.GITHUB_TOKEN_SECRET,
    show_default=True,
)
@new_optgroup("Outputs")
@optgroup.option(
    "--results",
    type=str,
    default=constants.RESULTS_DIR,
    help="""Specify the results directory on the container (an absolute path).
    This is where the results dataset will be mounted.""",
    show_default=True,
)
@new_optgroup("Task settings")
@optgroup.option(
    "-t",
    "--task-name",
    type=str,
    help="""A name to assign to the task on Beaker.""",
    default="main",
    show_default=True,
)
@optgroup.option(
    "--priority",
    type=click.Choice([str(p.name) for p in BeakerJobPriority]),
    help="The job priority.",
)
@optgroup.option(
    "--task-timeout",
    type=str,
    help="""The Beaker job timeout, e.g. "24h". If a job runs longer than this it will canceled
    by Beaker.""",
    show_default=True,
)
@optgroup.option(
    "--preemptible/--not-preemptible",
    is_flag=True,
    help="""Mark the job as preemptible or not. If you don't specify at least one cluster then
    jobs will default to preemptible.""",
    default=None,
)
@optgroup.option(
    "--retries", type=int, help="""Specify the number of automatic retries for the experiment."""
)
@new_optgroup("Multi-node")
@optgroup.option(
    "--replicas",
    type=int,
    help="""The number of task replicas to run.""",
)
@optgroup.option(
    "--leader-selection",
    is_flag=True,
    help="""Specifies that the first task replica should be the leader and populates each task
    with 'BEAKER_LEADER_REPLICA_HOSTNAME' and 'BEAKER_LEADER_REPLICA_NODE_ID' environment variables.
    This is only applicable when '--replicas INT' and '--host-networking' are used,
    although the '--host-networking' flag can be omitted in this case since it's assumed.""",
)
@optgroup.option(
    "--host-networking",
    is_flag=True,
    help="""Specifies that each task replica should use the host's network.
    When used with '--replicas INT', this allows the replicas to communicate with each
    other using their hostnames.""",
)
@optgroup.option(
    "--propagate-failure", is_flag=True, help="""Stop the experiment if any task fails."""
)
@optgroup.option(
    "--propagate-preemption", is_flag=True, help="""Stop the experiment if any task is preempted."""
)
@optgroup.option(
    "--synchronized-start-timeout",
    type=str,
    help="""
    If set, jobs in the replicated task will wait this long to start until all other jobs are also ready.
    """,
)
@new_optgroup("Python")
@optgroup.option(
    "--conda",
    type=click.Path(exists=True, dir_okay=False),
    help=f"""Path to a conda environment file for reconstructing your Python environment.
    If not specified, '{constants.CONDA_ENV_FILE}' will be used if it exists.""",
)
@optgroup.option(
    "--venv",
    type=str,
    help="""The name of an existing conda environment on the image to use.""",
)
@optgroup.option(
    "--pip",
    type=click.Path(exists=True, dir_okay=False),
    help=f"""Path to a PIP requirements file for reconstructing your Python environment.
    If not specified, '{constants.PIP_REQUIREMENTS_FILE}' will be used if it exists.""",
)
@optgroup.option(
    "--install",
    type=str,
    help="""Override the default Python installation command, e.g. '--install "python setup.py install"'.""",
)
@optgroup.option(
    "--no-conda",
    is_flag=True,
    help="""If set, gantry will skip setting up conda to construct a Python environment
    and instead will use the default Python environment on the image.""",
)
@optgroup.option(
    "--no-python",
    is_flag=True,
    help="""If set, gantry will skip setting up a Python environment altogether.""",
)
def run(
    arg: Tuple[str, ...],
    name: Optional[str] = None,
    description: Optional[str] = None,
    task_name: str = "main",
    workspace: Optional[str] = None,
    group_name: Optional[str] = None,
    cluster: Optional[Tuple[str, ...]] = None,
    hostname: Optional[Tuple[str, ...]] = None,
    beaker_image: Optional[str] = None,
    docker_image: Optional[str] = None,
    cpus: Optional[float] = None,
    gpus: Optional[int] = None,
    memory: Optional[str] = None,
    shared_memory: Optional[str] = None,
    dataset: Optional[Tuple[str, ...]] = None,
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET,
    ref: Optional[str] = None,
    branch: Optional[str] = None,
    conda: Optional[PathOrStr] = None,
    pip: Optional[PathOrStr] = None,
    venv: Optional[str] = None,
    env: Optional[Tuple[str, ...]] = None,
    env_secret: Optional[Tuple[str, ...]] = None,
    dataset_secret: Optional[Tuple[str, ...]] = None,
    timeout: int = 0,
    task_timeout: Optional[str] = None,
    show_logs: bool = True,
    allow_dirty: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    save_spec: Optional[PathOrStr] = None,
    priority: Optional[str] = None,
    install: Optional[str] = None,
    no_python: bool = False,
    no_conda: bool = False,
    replicas: Optional[int] = None,
    leader_selection: bool = False,
    host_networking: bool = False,
    propagate_failure: Optional[bool] = None,
    propagate_preemption: Optional[bool] = None,
    synchronized_start_timeout: Optional[str] = None,
    mount: Optional[Tuple[str, ...]] = None,
    weka: Optional[str] = None,
    budget: Optional[str] = None,
    preemptible: Optional[bool] = None,
    retries: Optional[int] = None,
    results: str = constants.RESULTS_DIR,
):
    """
    Run an experiment on Beaker.

    Example:

    $ gantry run --yes --timeout=-1 -- python -c 'print("Hello, World!")'
    """

    validate_args(arg)

    if install:
        if no_python:
            raise ConfigurationError("--no-python and --install='...' are mutually exclusive.")
        if pip:
            raise ConfigurationError("--pip='...' and --install='...' are mutually exclusive.")

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
    git_config = GitConfig.from_env(ref=ref, branch=branch)

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
        group: Optional[BeakerGroup] = None
        if group_name is not None:
            group = util.resolve_group(beaker, group_name)
            if group is None:
                if prompt.Confirm.ask(
                    f"Group [green]{group_name}[/] not found in workspace, would you like to create this group?"
                ):
                    group = beaker.group.create(group_name)
                    print(f"Group created: {util.group_url(beaker, group)}")
                else:
                    print_stderr("[yellow]canceled[/]")
                    sys.exit(1)

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
        datasets_to_use = ensure_datasets(beaker, *dataset) if dataset else []

        env_vars = []
        for e in env or []:
            try:
                env_name, val = e.split("=", 1)
            except ValueError:
                raise ValueError("Invalid --env option: {e}")
            env_vars.append((env_name, val))

        env_secrets = []
        for e in env_secret or []:
            try:
                env_secret_name, secret = e.split("=", 1)
            except ValueError:
                raise ValueError(f"Invalid --env-secret option: '{e}'")
            env_secrets.append((env_secret_name, secret))

        dataset_secrets = []
        for ds in dataset_secret or []:
            try:
                secret, mount_path = ds.split(":", 1)
            except ValueError:
                raise ValueError(f"Invalid --dataset-secret option: '{ds}'")
            dataset_secrets.append((secret, mount_path))

        mounts = []
        for m in mount or []:
            try:
                source, target = m.split(":", 1)
            except ValueError:
                raise ValueError(f"Invalid --mount option: '{m}'")
            mounts.append((source, target))

        weka_buckets = []
        for m in weka or []:
            try:
                source, target = m.split(":", 1)
            except ValueError:
                raise ValueError(f"Invalid --weka option: '{m}'")
            weka_buckets.append((source, target))

        # Validate clusters.
        if cluster:
            cl_objects = list(beaker.cluster.list())
            final_clusters = []
            for pat in cluster:
                org = beaker.org_name

                og_pat = pat
                if "/" in pat:
                    org, pat = pat.split("/", 1)

                matching_clusters = [
                    f"{cl.organization_name}/{cl.name}"
                    for cl in cl_objects
                    if fnmatch(cl.name, pat) and cl.organization_name == org
                ]

                if matching_clusters:
                    final_clusters.extend(matching_clusters)
                else:
                    raise ConfigurationError(
                        f"cluster '{og_pat}' did not match any Beaker clusters"
                    )
            cluster = list(set(final_clusters))  # type: ignore

        # Default to preemptible when no cluster has been specified.
        if not cluster and preemptible is None:
            preemptible = True

        # Initialize experiment and task spec.
        spec = build_experiment_spec(
            task_name=task_name,
            clusters=list(cluster or []),
            task_resources=task_resources,
            arguments=list(arg),
            entrypoint_dataset=entrypoint_dataset.id,
            git_config=git_config,
            budget=budget,
            description=description,
            beaker_image=beaker_image,
            docker_image=docker_image,
            gh_token_secret=gh_token_secret if not git_config.is_public else None,
            conda=conda,
            pip=pip,
            venv=venv,
            datasets=datasets_to_use,
            env=env_vars,
            env_secrets=env_secrets,
            dataset_secrets=dataset_secrets,
            priority=priority,
            install=install,
            no_python=no_python,
            no_conda=no_conda,
            replicas=replicas,
            leader_selection=leader_selection,
            host_networking=host_networking or (bool(replicas) and leader_selection),
            propagate_failure=propagate_failure,
            propagate_preemption=propagate_preemption,
            synchronized_start_timeout=synchronized_start_timeout,
            task_timeout=task_timeout,
            mounts=mounts,
            weka_buckets=weka_buckets,
            hostnames=None if hostname is None else list(hostname),
            preemptible=preemptible,
            retries=retries,
            results=results,
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
                f"[b]Group:[/] {None if group is None else util.group_url(beaker, group)}\n"
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

        if group is not None:
            beaker.group.update(group, add_experiment_ids=[workload.experiment.id])
            print(f"Group URL: {util.group_url(beaker, group)}")

        # Can return right away if timeout is 0.
        if timeout == 0:
            return

        job: Optional[BeakerJob] = None
        try:
            job = util.follow_workload(beaker, workload, timeout=timeout, show_logs=show_logs)
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


def build_experiment_spec(
    *,
    task_name: str,
    clusters: List[str],
    task_resources: BeakerTaskResources,
    arguments: List[str],
    entrypoint_dataset: str,
    git_config: GitConfig,
    budget: Optional[str] = None,
    description: Optional[str] = None,
    beaker_image: Optional[str] = None,
    docker_image: Optional[str] = None,
    gh_token_secret: Optional[str] = constants.GITHUB_TOKEN_SECRET,
    conda: Optional[PathOrStr] = None,
    pip: Optional[PathOrStr] = None,
    venv: Optional[str] = None,
    datasets: Optional[List[Tuple[str, Optional[str], str]]] = None,
    env: Optional[List[Tuple[str, str]]] = None,
    env_secrets: Optional[List[Tuple[str, str]]] = None,
    dataset_secrets: Optional[List[Tuple[str, str]]] = None,
    priority: Optional[Union[str, BeakerJobPriority]] = None,
    install: Optional[str] = None,
    no_python: bool = False,
    no_conda: bool = False,
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
):
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

    for name, val in env or []:
        task_spec = task_spec.with_env_var(name=name, value=val)

    for name, secret in env_secrets or []:
        task_spec = task_spec.with_env_var(name=name, secret=secret)

    if no_python:
        task_spec = task_spec.with_env_var(name="NO_PYTHON", value="1")
    else:
        if not no_conda:
            if conda is not None:
                task_spec = task_spec.with_env_var(
                    name="CONDA_ENV_FILE",
                    value=str(conda),
                )
            elif Path(constants.CONDA_ENV_FILE).is_file():
                task_spec = task_spec.with_env_var(
                    name="CONDA_ENV_FILE",
                    value=constants.CONDA_ENV_FILE,
                )
            elif Path(constants.CONDA_ENV_FILE_ALTERNATE).is_file():
                task_spec = task_spec.with_env_var(
                    name="CONDA_ENV_FILE",
                    value=constants.CONDA_ENV_FILE_ALTERNATE,
                )
            else:
                task_spec = task_spec.with_env_var(
                    name="PYTHON_VERSION", value=".".join(platform.python_version_tuple()[:-1])
                )

            if venv is not None:
                task_spec = task_spec.with_env_var(
                    name="VENV_NAME",
                    value=venv,
                )
        else:
            task_spec = task_spec.with_env_var(name="NO_CONDA", value="1")

        if pip is not None:
            task_spec = task_spec.with_env_var(
                name="PIP_REQUIREMENTS_FILE",
                value=str(pip),
            )

        if install is not None:
            task_spec = task_spec.with_env_var(name="INSTALL_CMD", value=install)

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

    return BeakerExperimentSpec(
        description=description,
        budget=budget,
        tasks=[task_spec],
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


def validate_args(arg: Tuple[str, ...]):
    if not arg:
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
    invalid_args = arg[: -len(given_args)]
    if invalid_args:
        raise ConfigurationError(
            f"Invalid options, found extra arguments before the '--': "
            f"{', '.join([repr(s) for s in invalid_args])}.\n"
            "Hint: you might be trying to pass a value to a FLAG option.\n"
            "Try 'gantry run --help' for help."
        )
