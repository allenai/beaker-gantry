import sys
from typing import Optional, Tuple

import click
import rich
from beaker import (
    Beaker,
    ExperimentSpec,
    SecretNotFound,
    TaskResources,
    TaskSpec,
    WorkspaceNotSet,
)
from click_help_colors import HelpColorsCommand, HelpColorsGroup
from rich import print, prompt, traceback

from .common import constants, util
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
    elif issubclass(exctype, (KeyboardInterrupt,)):
        sys.__excepthook__(exctype, value, tb)
    else:
        print_stderr(traceback.Traceback.from_exception(exctype, value, tb, suppress=[click]))


sys.excepthook = excepthook


@click.group(**_CLICK_GROUP_DEFAULTS)
@click.version_option(version=VERSION)
def main():
    rich.get_console().print(
        '''[cyan b]
   __ _                    _               _  _
  / _` |  __ _    _ _     | |_      _ _   | || |
  \__, | / _` |  | ' \    |  _|    | '_|   \_, |
  |___/  \__,_|  |_||_|   _\__|   _|_|_   _|__/  [/][blue]
_|"""""|_|"""""|_|"""""|_|"""""|_|"""""|_| """"|
"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-'
[/]''',  # noqa: W605
        highlight=False,
    )


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
    help="""Allow submitted the experiment with a dirty working directory.""",
)
@click.option("--dry-run", is_flag=True, help="""Do a dry run only.""")
def run(
    arg: Tuple[str, ...],
    name: Optional[str] = None,
    description: Optional[str] = None,
    task_name: str = "main",
    workspace: Optional[str] = None,
    cluster: Tuple[str, ...] = (constants.DEFAULT_CLUSTER,),
    cpus: Optional[float] = None,
    gpus: Optional[int] = None,
    memory: Optional[str] = None,
    shared_memory: Optional[str] = None,
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET,
    timeout: int = 0,
    allow_dirty: bool = False,
    dry_run: bool = False,
):
    """
    Run an experiment on Beaker.

    E.g.

    $ gantry run --name 'hello-world' -- python -c 'Hello, World!'
    """
    if not arg:
        raise ConfigurationError("[ARGS]... are required!")

    name: str = name or prompt.Prompt.ask(  # type: ignore[assignment]
        "[i]What would you like to call this experiment?[/]", default=util.unique_name()
    )

    task_resources = TaskResources(
        cpu_count=cpus, gpu_count=gpus, memory=memory, shared_memory=shared_memory
    )

    # Initialize Beaker client and validate workspace.
    beaker = (
        Beaker.from_env() if workspace is None else Beaker.from_env(default_workspace=workspace)
    )
    try:
        if beaker.workspace.get_permissions().public:
            raise WorkspacePermissionsError(
                f"Your workspace {beaker.workspace.url()} is public! "
                f"Public workspaces are not allowed."
            )
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

    # Initialize experiment spec.
    spec = ExperimentSpec(
        description=description,
        tasks=[
            TaskSpec.new(
                task_name,
                cluster_to_use,
                beaker_image=constants.DEFAULT_IMAGE,
                result_path="/results",
                command=["bash", "/gantry/entrypoint.sh"],
                arguments=list(arg),
                resources=task_resources,
            )
            .with_env_var(name="GITHUB_TOKEN", secret=gh_token_secret)
            .with_env_var(name="GITHUB_REPO", value=f"{github_account}/{github_repo}")
            .with_env_var(name="GIT_REF", value=git_ref)
            .with_dataset("/gantry", beaker=entrypoint_dataset.id)
        ],
    )

    if dry_run:
        print("Dry run experiment spec:", spec.to_json())
        return

    experiment = beaker.experiment.create(name, spec)
    print(f"Experiment submitted, see progress at {beaker.experiment.url(experiment)}")

    # Can return right away if timeout is 0.
    if timeout == 0:
        return

    try:
        experiment = beaker.experiment.wait_for(experiment, timeout=timeout)[0]
    except (KeyboardInterrupt, TimeoutError):
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
    print()
    rich.get_console().rule(f"Logs from task [i]'{task.display_name}'[/]")
    util.display_logs(beaker.job.logs(job, quiet=True))

    if exit_code > 0:
        raise ExperimentFailedError(f"Experiment exited with non-zero code ({exit_code})")


if __name__ == "__main__":
    traceback.install()
    main()
