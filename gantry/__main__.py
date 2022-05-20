import os
import signal
import sys
from pathlib import Path
from typing import Optional, Tuple

import click
import rich
from beaker import Beaker, SecretNotFound, TaskResources, WorkspaceNotSet
from click_help_colors import HelpColorsCommand, HelpColorsGroup
from rich import pretty, print, prompt, traceback

from .common import constants, util
from .common.aliases import PathOrStr
from .common.util import print_stderr
from .exceptions import *
from .version import VERSION

_CLICK_GROUP_DEFAULTS = {
    "cls": HelpColorsGroup,
    "help_options_color": "green",
    "help_headers_color": "yellow",
    "context_settings": {"max_content_width": 115},
}

_CLICK_COMMAND_DEFAULTS = {
    "cls": HelpColorsCommand,
    "help_options_color": "green",
    "help_headers_color": "yellow",
    "context_settings": {"max_content_width": 115},
}


def excepthook(exctype, value, tb):
    """
    Used to patch `sys.excepthook` in order to customize handling of uncaught exceptions.
    """
    # Ignore `GantryError` because we don't need a traceback for those.
    if issubclass(exctype, (GantryError,)):
        print_stderr(f"[red][bold]{exctype.__name__}:[/] [i]{value}[/][/]")
    # For interruptions, call the original exception handler.
    elif issubclass(exctype, (KeyboardInterrupt, TermInterrupt)):
        sys.__excepthook__(exctype, value, tb)
    else:
        print_stderr(traceback.Traceback.from_exception(exctype, value, tb, suppress=[click]))


sys.excepthook = excepthook


def handle_sigterm(sig, frame):
    raise TermInterrupt


@click.group(**_CLICK_GROUP_DEFAULTS)
@click.version_option(version=VERSION)
def main():
    # Configure rich.
    if os.environ.get("GANTRY_GITHUB_TESTING"):
        # Force a broader terminal when running tests in GitHub Actions.
        console_width = 180
        rich.reconfigure(width=console_width, force_terminal=True, force_interactive=False)
        pretty.install()
    else:
        pretty.install()

    # Handle SIGTERM just like KeyboardInterrupt
    signal.signal(signal.SIGTERM, handle_sigterm)

    rich.get_console().print(
        '''
[cyan b]                                             o=======[]   [/]
[cyan b]   __ _                    _               _ |_      []   [/]
[cyan b]  / _` |  __ _    _ _     | |_      _ _   | || |     []   [/]
[cyan b]  \__, | / _` |  | ' \    |  _|    | '_|   \_, |   _/ ]_  [/]
[cyan b]  |___/  \__,_|  |_||_|   _\__|   _|_|_   _|__/   |_____| [/]
[blue b]_|"""""|_|"""""|_|"""""|_|"""""|_|"""""|_| """"| [/]
[blue b] `---------------------------------------------' [/]
''',  # noqa: W605
        highlight=False,
    )

    util.check_for_upgrades()


@main.command(**_CLICK_COMMAND_DEFAULTS)
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
    default=[constants.DEFAULT_CLUSTER],
    help="""A potential cluster to use. If multiple are given,
    the first one with enough free resources to run the experiment is picked.""",
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
    type=int,
    help="""Minimum available system memory as a number with unit suffix (e.g. 2.5GiB).""",
)
@click.option(
    "--shared-memory",
    type=int,
    help="""Size of /dev/shm as a number with unit suffix (e.g. 2.5GiB).""",
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
    help="""Whether or not to print the logs to stdout when the experiment finalizes.""",
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
def run(
    arg: Tuple[str, ...],
    name: Optional[str] = None,
    description: Optional[str] = None,
    task_name: str = "main",
    workspace: Optional[str] = None,
    cluster: Tuple[str, ...] = (constants.DEFAULT_CLUSTER,),
    beaker_image: Optional[str] = constants.DEFAULT_IMAGE,
    docker_image: Optional[str] = None,
    cpus: Optional[float] = None,
    gpus: Optional[int] = None,
    memory: Optional[str] = None,
    shared_memory: Optional[str] = None,
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET,
    conda: Optional[PathOrStr] = None,
    pip: Optional[PathOrStr] = None,
    timeout: int = 0,
    nfs: Optional[bool] = None,
    show_logs: bool = True,
    allow_dirty: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    save_spec: Optional[PathOrStr] = None,
):
    """
    Run an experiment on Beaker.

    E.g.

    $ gantry run --name 'hello-world' -- python -c 'print("Hello, World!")'
    """
    if not arg:
        raise ConfigurationError("[ARGS]... are required!")

    if (beaker_image is None) == (docker_image is None):
        raise ConfigurationError(
            "Either --beaker-image or --docker-image must be specified, but not both."
        )

    task_resources = TaskResources(
        cpu_count=cpus, gpu_count=gpus, memory=memory, shared_memory=shared_memory
    )

    # Initialize Beaker client and validate workspace.
    beaker = (
        Beaker.from_env() if workspace is None else Beaker.from_env(default_workspace=workspace)
    )
    try:
        permissions = beaker.workspace.get_permissions()
        if len(permissions.authorizations) > 1:
            print_stderr(
                f"[yellow]Your workspace [b]{beaker.workspace.url()}[/] multiple contributors! "
                f"Every contributor can view your GitHub personal access token secret ('{gh_token_secret}').[/]"
            )
            if not yes and not prompt.Confirm.ask(
                "[yellow][i]Are you sure you want to use this workspace?[/][/]"
            ):
                raise KeyboardInterrupt
        elif workspace is None:
            default_workspace = beaker.workspace.get()
            if not yes and not prompt.Confirm.ask(
                f"Using default workspace [b cyan]{default_workspace.full_name}[/]. [i]Is that correct?[/]"
            ):
                raise KeyboardInterrupt
    except WorkspaceNotSet:
        raise ConfigurationError(
            "'--workspace' option is required since you don't have a default workspace set"
        )

    # Get repository account, name, and current ref.
    github_account, github_repo, git_ref = util.ensure_repo(allow_dirty)

    # Get the entrypoint dataset.
    entrypoint_dataset = util.ensure_entrypoint_dataset(beaker)

    # Get / set the GitHub token secret.
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
        print(f"GitHub token secret uploaded to workspace as '{gh_token_secret}'")

    gh_token_secret = util.ensure_github_token_secret(beaker, gh_token_secret)

    # Find a cluster to use.
    cluster_to_use = util.ensure_cluster(beaker, task_resources, *cluster)

    # Initialize experiment and task spec.
    spec = util.build_experiment_spec(
        task_name=task_name,
        cluster_to_use=cluster_to_use,
        task_resources=task_resources,
        arguments=list(arg),
        entrypoint_dataset=entrypoint_dataset.id,
        github_account=github_account,
        github_repo=github_repo,
        git_ref=git_ref,
        description=description,
        beaker_image=beaker_image,
        docker_image=docker_image,
        conda=conda,
        pip=pip,
        nfs=nfs,
    )

    if save_spec:
        if (
            Path(save_spec).is_file()
            and not yes
            and not prompt.Confirm.ask(
                f"[yellow]The file '{save_spec}' already exists. [i]Are you sure you want to overwrite it?[/][/]"
            )
        ):
            raise KeyboardInterrupt
        spec.to_file(save_spec)
        print(f"Experiment spec saved to {save_spec}")

    if dry_run:
        rich.get_console().rule("[b]Dry run[/]")
        print(
            f"[b]Workspace:[/] {beaker.workspace.url()}\n"
            f"[b]Cluster:[/] {beaker.cluster.url(cluster_to_use)}\n"
            f"[b]Commit:[/] https://github.com/{github_account}/{github_repo}/commit/{git_ref}\n"
            f"[b]Experiment spec:[/]",
            spec.to_json(),
        )
        return

    name: str = name or prompt.Prompt.ask(  # type: ignore[assignment]
        "[i]What would you like to call this experiment?[/]", default=util.unique_name()
    )
    if not name:
        raise ConfigurationError("Experiment name cannot be empty!")

    experiment = beaker.experiment.create(name, spec)
    print(f"Experiment submitted, see progress at {beaker.experiment.url(experiment)}")

    # Can return right away if timeout is 0.
    if timeout == 0:
        return

    try:
        experiment = beaker.experiment.wait_for(
            experiment, timeout=timeout if timeout > 0 else None
        )[0]
    except (KeyboardInterrupt, TermInterrupt, TimeoutError):
        print_stderr("[yellow]Canceling experiment...[/]")
        beaker.experiment.stop(experiment)
        raise

    # Get job and its exit code.
    exit_code = 0
    task = beaker.experiment.tasks(experiment)[0]
    job = task.latest_job
    assert job is not None
    if job.status.exit_code is not None and job.status.exit_code > 0:
        exit_code = job.status.exit_code

    # Display the logs.
    if show_logs:
        print()
        rich.get_console().rule(f"Logs from task [i]'{task.display_name}'[/]")
        util.display_logs(beaker.job.logs(job, quiet=True))
        rich.get_console().rule("End logs")
        print()

    if exit_code > 0:
        raise ExperimentFailedError(f"Experiment exited with non-zero code ({exit_code})")

    assert job.execution is not None
    assert job.status.started is not None
    assert job.status.exited is not None

    print(
        f"[b green]\N{check mark}[/] [b cyan]{name}[/] completed successfully\n"
        f"[b]Experiment:[/] {beaker.experiment.url(experiment)}\n"
        f"[b]Runtime:[/] {util.format_timedelta(job.status.exited - job.status.started)}\n"
        f"[b]Results:[/] {beaker.dataset.url(job.execution.result.beaker)}"
    )

    metrics = beaker.experiment.metrics(experiment)
    if metrics is not None:
        print("[b]Metrics:[/]", metrics)


if __name__ == "__main__":
    main()
