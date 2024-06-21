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
    ExperimentConflict,
    ExperimentSpec,
    ImageNotFound,
    Job,
    JobTimeoutError,
    Priority,
    SecretNotFound,
    TaskResources,
    TaskSpec,
)
from rich import print, prompt

from .. import constants, util
from ..aliases import PathOrStr
from ..exceptions import *
from ..util import print_stderr
from ..version import VERSION
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("arg", nargs=-1)
@click.option(
    "-n",
    "--name",
    type=str,
    help="""A name to assign to the experiment on Beaker. Defaults to a randomly generated name.""",
)
@click.option(
    "-t",
    "--task-name",
    type=str,
    help="""A name to assign to the task on Beaker.""",
    default="main",
    show_default=True,
)
@click.option("-d", "--description", type=str, help="""A description for the experiment.""")
@click.option(
    "-w",
    "--workspace",
    type=str,
    help="""The Beaker workspace to use.
    If not specified, your default workspace will be used.""",
)
@click.option(
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
@click.option(
    "--hostname",
    type=str,
    multiple=True,
    default=None,
    help="""Hostname constraints to apply to the experiment spec. This option can be used multiple times to allow
    multiple hosts.""",
    show_default=True,
)
@click.option(
    "--beaker-image",
    type=str,
    default=constants.DEFAULT_IMAGE,
    help="""The name or ID of an image on Beaker to use for your experiment.
    Mutually exclusive with --docker-image.""",
    show_default=True,
)
@click.option(
    "--docker-image",
    type=str,
    help="""The name of a public Docker image to use for your experiment.
    Mutually exclusive with --beaker-image.""",
)
@click.option(
    "--cpus",
    type=float,
    help="""Minimum number of logical CPU cores (e.g. 4.0, 0.5).""",
)
@click.option(
    "--gpus",
    type=int,
    help="""Minimum number of GPUs (e.g. 1).""",
)
@click.option(
    "--memory",
    type=str,
    help="""Minimum available system memory as a number with unit suffix (e.g. 2.5GiB).""",
)
@click.option(
    "--shared-memory",
    type=str,
    help="""Size of /dev/shm as a number with unit suffix (e.g. 2.5GiB).""",
)
@click.option(
    "--dataset",
    type=str,
    multiple=True,
    help="""An input dataset in the form of 'dataset-name:/mount/location' or
    'dataset-name:sub/path:/mount/location' to attach to your experiment.
    You can specify this option more than once to attach multiple datasets.""",
)
@click.option(
    "--gh-token-secret",
    type=str,
    help="""The name of the Beaker secret that contains your GitHub token.""",
    default=constants.GITHUB_TOKEN_SECRET,
    show_default=True,
)
@click.option(
    "--conda",
    type=click.Path(exists=True, dir_okay=False),
    help=f"""Path to a conda environment file for reconstructing your Python environment.
    If not specified, '{constants.CONDA_ENV_FILE}' will be used if it exists.""",
)
@click.option(
    "--pip",
    type=click.Path(exists=True, dir_okay=False),
    help=f"""Path to a PIP requirements file for reconstructing your Python environment.
    If not specified, '{constants.PIP_REQUIREMENTS_FILE}' will be used if it exists.""",
)
@click.option(
    "--venv",
    type=str,
    help="""The name of an existing conda environment on the image to use.""",
)
@click.option(
    "--env",
    type=str,
    help="""Environment variables to add the Beaker experiment. Should be in the form '{NAME}={VALUE}'.""",
    multiple=True,
)
@click.option(
    "--env-secret",
    type=str,
    help="""Environment variables to add the Beaker experiment from Beaker secrets.
    Should be in the form '{NAME}={SECRET_NAME}'.""",
    multiple=True,
)
@click.option(
    "--nfs / --no-nfs",
    default=None,
    help=f"""Whether or not to mount the NFS drive ({constants.NFS_MOUNT}) to the experiment.
    This only works for cirrascale clusters managed by the Beaker team.
    If not specified, gantry will always mount NFS when it knows the cluster supports it.""",
)
@click.option(
    "--show-logs/--no-logs",
    default=True,
    show_default=True,
    help="""Whether or not to stream the logs to stdout as the experiment runs.
    This only takes effect when --timeout is non-zero.""",
)
@click.option(
    "--timeout",
    type=int,
    default=0,
    help="""Time to wait (in seconds) for the experiment to finish.
    A timeout of -1 means wait indefinitely.
    A timeout of 0 means don't wait at all.""",
    show_default=True,
)
@click.option(
    "--allow-dirty",
    is_flag=True,
    help="""Allow submitting the experiment with a dirty working directory.""",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="""Skip all confirmation prompts.""",
)
@click.option("--dry-run", is_flag=True, help="""Do a dry run only.""")
@click.option(
    "--save-spec",
    type=click.Path(dir_okay=False, file_okay=True),
    help="""A path to save the generated Beaker experiment spec to.""",
)
@click.option(
    "--priority",
    type=click.Choice([str(p) for p in Priority]),
    help="The job priority. If you don't specify at least one cluster, priority will default to 'preemptible'.",
)
@click.option(
    "--install",
    type=str,
    help="""Override the default installation command, e.g. '--install "python setup.py install"'""",
)
@click.option(
    "--no-python",
    is_flag=True,
    help="""If set, gantry will skip setting up a Python environment altogether.""",
)
@click.option(
    "--replicas",
    type=int,
    help="""The number of task replicas to run.""",
)
@click.option(
    "--leader-selection",
    is_flag=True,
    help="""Specifies that the first task replica should be the leader and populates each task
    with 'BEAKER_LEADER_REPLICA_HOSTNAME' and 'BEAKER_LEADER_REPLICA_NODE_ID' environment variables.
    This is only applicable when '--replicas INT' and '--host-networking' are used,
    although the '--host-networking' flag can be omitted in this case since it's assumed.""",
)
@click.option(
    "--host-networking",
    is_flag=True,
    help="""Specifies that each task replica should use the host's network.
    When used with '--replicas INT', this allows the replicas to communicate with each
    other using their hostnames.""",
)
@click.option(
    "--propagate-failure", is_flag=True, help="""Stop the experiment if any task fails."""
)
@click.option(
    "--propagate-preemption", is_flag=True, help="""Stop the experiment if any task is preempted."""
)
@click.option(
    "--synchronized-start-timeout",
    type=str,
    help="""
    If set, jobs in the replicated task will wait this long to start until all other jobs are also ready.
    """,
)
@click.option(
    "-m",
    "--mount",
    type=str,
    help="""Host directories to mount to the Beaker experiment. Should be in the form '{HOST_SOURCE}:{TARGET}'
    similar to the '-v' option with 'docker run'.""",
    multiple=True,
)
@click.option(
    "--weka",
    type=str,
    multiple=True,
    help="""A weka bucket to mount in the form of 'bucket-name:/mount/location',
    e.g. --weka=oe-training-default:/data""",
)
@click.option(
    "-b", "--budget", type=str, help="""The budget account to associate with the experiment."""
)
@click.option("--preemptible", is_flag=True, help="""Mark the job as preemptible.""")
@click.option("--stop-preemptible", is_flag=True, help="""Stop all preemptible on the cluster.""")
def run(
    arg: Tuple[str, ...],
    name: Optional[str] = None,
    description: Optional[str] = None,
    task_name: str = "main",
    workspace: Optional[str] = None,
    cluster: Optional[Tuple[str, ...]] = None,
    hostname: Optional[Tuple[str, ...]] = None,
    beaker_image: Optional[str] = constants.DEFAULT_IMAGE,
    docker_image: Optional[str] = None,
    cpus: Optional[float] = None,
    gpus: Optional[int] = None,
    memory: Optional[str] = None,
    shared_memory: Optional[str] = None,
    dataset: Optional[Tuple[str, ...]] = None,
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET,
    conda: Optional[PathOrStr] = None,
    pip: Optional[PathOrStr] = None,
    venv: Optional[str] = None,
    env: Optional[Tuple[str, ...]] = None,
    env_secret: Optional[Tuple[str, ...]] = None,
    timeout: int = 0,
    nfs: Optional[bool] = None,
    show_logs: bool = True,
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
    mount: Optional[Tuple[str, ...]] = None,
    weka: Optional[str] = None,
    budget: Optional[str] = None,
    preemptible: bool = False,
    stop_preemptible: bool = False,
):
    """
    Run an experiment on Beaker.

    Example:

    $ gantry run --name 'hello-world' -- python -c 'print("Hello, World!")'
    """
    if not arg:
        raise ConfigurationError(
            "[ARGS]... are required! For example:\n$ gantry run -- python -c 'print(\"Hello, World!\")'"
        )

    if (beaker_image is None) == (docker_image is None):
        raise ConfigurationError(
            "Either --beaker-image or --docker-image must be specified, but not both."
        )

    if budget is None:
        budget = prompt.Prompt.ask(
            "[yellow]Missing '--budget' option, "
            "see https://beaker-docs.apps.allenai.org/concept/budgets.html for more information.[/]\n"
            "[i]Please enter the budget account to associate with this experiment[/]",
        )

    if not budget:
        raise ConfigurationError("Budget account must be specified!")

    task_resources = TaskResources(
        cpu_count=cpus, gpu_count=gpus, memory=memory, shared_memory=shared_memory
    )

    # Get repository account, name, and current ref.
    github_account, github_repo, git_ref, is_public = util.ensure_repo(allow_dirty)

    # Initialize Beaker client and validate workspace.
    beaker = util.ensure_workspace(
        workspace=workspace, yes=yes, gh_token_secret=gh_token_secret, public_repo=is_public
    )

    if beaker_image is not None and beaker_image != constants.DEFAULT_IMAGE:
        try:
            beaker_image = beaker.image.get(beaker_image).full_name
        except ImageNotFound:
            raise ConfigurationError(f"Beaker image '{beaker_image}' not found")

    # Get the entrypoint dataset.
    entrypoint_dataset = util.ensure_entrypoint_dataset(beaker)

    # Get / set the GitHub token secret.
    if not is_public:
        try:
            beaker.secret.get(gh_token_secret)
        except SecretNotFound:
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
            env_name, val = e.split("=")
        except ValueError:
            raise ValueError("Invalid --env option: {e}")
        env_vars.append((env_name, val))

    env_secrets = []
    for e in env_secret or []:
        try:
            env_secret_name, secret = e.split("=")
        except ValueError:
            raise ValueError(f"Invalid --env-secret option: '{e}'")
        env_secrets.append((env_secret_name, secret))

    mounts = []
    for m in mount or []:
        try:
            source, target = m.split(":")
        except ValueError:
            raise ValueError(f"Invalid --mount option: '{m}'")
        mounts.append((source, target))

    weka_buckets = []
    for m in weka or []:
        try:
            source, target = m.split(":")
        except ValueError:
            raise ValueError(f"Invalid --weka option: '{m}'")
        weka_buckets.append((source, target))

    # Validate clusters.
    if cluster:
        cl_objects = beaker.cluster.list()
        final_clusters = []
        for pat in cluster:
            matching_clusters = [cl.full_name for cl in cl_objects if fnmatch(cl.full_name, pat)]
            if matching_clusters:
                final_clusters.extend(matching_clusters)
            else:
                raise ConfigurationError(f"cluster '{pat}' did not match any Beaker clusters")
        cluster = list(set(final_clusters))  # type: ignore

    # Default to preemptible priority when no cluster has been specified.
    if not cluster and priority is None:
        priority = Priority.preemptible

    # Initialize experiment and task spec.
    spec = build_experiment_spec(
        task_name=task_name,
        clusters=list(cluster or []),
        task_resources=task_resources,
        arguments=list(arg),
        entrypoint_dataset=entrypoint_dataset.id,
        github_account=github_account,
        github_repo=github_repo,
        git_ref=git_ref,
        budget=budget,
        description=description,
        beaker_image=beaker_image,
        docker_image=docker_image,
        gh_token_secret=gh_token_secret if not is_public else None,
        conda=conda,
        pip=pip,
        venv=venv,
        nfs=nfs,
        datasets=datasets_to_use,
        env=env_vars,
        env_secrets=env_secrets,
        priority=priority,
        install=install,
        no_python=no_python,
        replicas=replicas,
        leader_selection=leader_selection,
        host_networking=host_networking or (bool(replicas) and leader_selection),
        propagate_failure=propagate_failure,
        propagate_preemption=propagate_preemption,
        synchronized_start_timeout=synchronized_start_timeout,
        mounts=mounts,
        weka_buckets=weka_buckets,
        hostnames=None if hostname is None else list(hostname),
        preemptible=preemptible,
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
            f"[b]Commit:[/] https://github.com/{github_account}/{github_repo}/commit/{git_ref}\n"
            f"[b]Name:[/] {name}\n"
            f"[b]Experiment spec:[/]",
            spec.to_json(),
        )
        return

    name_prefix = name
    while True:
        try:
            experiment = beaker.experiment.create(name, spec)
            break
        except ExperimentConflict:
            name = (
                name_prefix
                + "-"
                + random.choice(string.ascii_lowercase)
                + random.choice(string.ascii_lowercase)
                + random.choice(string.digits)
                + random.choice(string.digits)
            )

    print(f"Experiment submitted, see progress at {beaker.experiment.url(experiment)}")

    if stop_preemptible:
        if priority == Priority.preemptible:
            print_stderr("[yellow]You cannot preempt other jobs when your job is preemptible.[/]")
        elif not cluster:
            print_stderr("[yellow]Preempt jobs requires specifying a cluster.[/]")
        elif len(cluster) > 1:
            print_stderr("[yellow]Preempt jobs requires specifying a single cluster.[/]")
        elif not dry_run:
            print(f"Preempting jobs on cluster {cluster[0]}...")
            preempted = beaker.cluster.preempt_jobs(cluster[0], ignore_failures=True)
            if preempted:
                print(f"Preempted {len(preempted)} jobs on cluster {cluster[0]}")
            else:
                print("No more jobs to preempt")

    # Can return right away if timeout is 0.
    if timeout == 0:
        return

    job: Optional[Job] = None
    try:
        if show_logs:
            job = util.follow_experiment(beaker, experiment, timeout=timeout)
        else:
            experiment = beaker.experiment.wait_for(
                experiment, timeout=timeout if timeout > 0 else None
            )[0]
            job = beaker.experiment.tasks(experiment)[0].latest_job  # type: ignore
            assert job is not None
    except (TermInterrupt, JobTimeoutError) as exc:
        print_stderr(f"[red][bold]{exc.__class__.__name__}:[/] [i]{exc}[/][/]")
        beaker.experiment.stop(experiment)
        print_stderr("[yellow]Experiment cancelled.[/]")
        sys.exit(1)
    except KeyboardInterrupt as exc:
        print_stderr(f"[red][bold]{exc.__class__.__name__}:[/] [i]{exc}[/][/]")
        print(f"See the experiment at {beaker.experiment.url(experiment)}")
        print_stderr(
            f"[yellow]To cancel the experiment, run:\n[i]$ gantry stop {experiment.id}[/][/]"
        )
        sys.exit(1)

    util.display_results(beaker, experiment, job)


def build_experiment_spec(
    *,
    task_name: str,
    clusters: List[str],
    task_resources: TaskResources,
    arguments: List[str],
    entrypoint_dataset: str,
    github_account: str,
    github_repo: str,
    git_ref: str,
    budget: str,
    description: Optional[str] = None,
    beaker_image: Optional[str] = None,
    docker_image: Optional[str] = None,
    gh_token_secret: Optional[str] = constants.GITHUB_TOKEN_SECRET,
    conda: Optional[PathOrStr] = None,
    pip: Optional[PathOrStr] = None,
    venv: Optional[str] = None,
    nfs: Optional[bool] = None,
    datasets: Optional[List[Tuple[str, Optional[str], str]]] = None,
    env: Optional[List[Tuple[str, str]]] = None,
    env_secrets: Optional[List[Tuple[str, str]]] = None,
    priority: Optional[Union[str, Priority]] = None,
    install: Optional[str] = None,
    no_python: bool = False,
    replicas: Optional[int] = None,
    leader_selection: bool = False,
    host_networking: bool = False,
    propagate_failure: Optional[bool] = None,
    propagate_preemption: Optional[bool] = None,
    synchronized_start_timeout: Optional[str] = None,
    mounts: Optional[List[Tuple[str, str]]] = None,
    weka_buckets: Optional[List[Tuple[str, str]]] = None,
    hostnames: Optional[List[str]] = None,
    preemptible: bool = False,
):
    task_spec = (
        TaskSpec.new(
            task_name,
            beaker_image=beaker_image,
            docker_image=docker_image,
            result_path=constants.RESULTS_DIR,
            command=["bash", "/gantry/entrypoint.sh"],
            arguments=arguments,
            resources=task_resources,
            priority=priority,
            replicas=replicas,
            leader_selection=leader_selection,
            host_networking=host_networking,
            propagate_failure=propagate_failure,
            propagate_preemption=propagate_preemption,
            synchronized_start_timeout=synchronized_start_timeout,
        )
        .with_env_var(name="GANTRY_VERSION", value=VERSION)
        .with_env_var(name="GITHUB_REPO", value=f"{github_account}/{github_repo}")
        .with_env_var(name="GIT_REF", value=git_ref)
        .with_env_var(name="GANTRY_TASK_NAME", value=task_name)
        .with_dataset("/gantry", beaker=entrypoint_dataset)
    )

    if preemptible:
        task_spec.context.preemptible = True

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

        if pip is not None:
            task_spec = task_spec.with_env_var(
                name="PIP_REQUIREMENTS_FILE",
                value=str(pip),
            )

        if venv is not None:
            task_spec = task_spec.with_env_var(
                name="VENV_NAME",
                value=venv,
            )

        if install is not None:
            task_spec = task_spec.with_env_var(name="INSTALL_CMD", value=install)

    if (
        nfs is None
        and clusters
        and all(
            [
                "cirrascale" in cluster and cluster not in constants.CLUSTERS_WITHOUT_NFS
                for cluster in clusters
            ]
        )
    ):
        nfs = True

    if nfs:
        task_spec = task_spec.with_dataset(constants.NFS_MOUNT, host_path=constants.NFS_MOUNT)

    if datasets:
        for dataset_id, sub_path, path in datasets:
            task_spec = task_spec.with_dataset(path, beaker=dataset_id, sub_path=sub_path)

    if mounts:
        for source, target in mounts:
            task_spec = task_spec.with_dataset(target, host_path=source)

    if weka_buckets:
        for source, target in weka_buckets:
            task_spec = task_spec.with_dataset(target, weka=source)

    return ExperimentSpec(description=description, budget=budget, tasks=[task_spec])


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
