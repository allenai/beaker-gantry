import logging
import sys
from typing import Sequence

import click
from beaker import BeakerJobPriority
from click_option_group import optgroup
from dataclass_extensions import decode

from .. import constants, utils
from ..callbacks import Callback, SlackCallback
from ..config import get_global_config
from ..exceptions import *
from ..recipe import Recipe
from .main import CLICK_COMMAND_DEFAULTS, main, new_optgroup

config = get_global_config()
log = logging.getLogger(__name__)


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.help_option("--help", help="Show this message and exit.")
@click.argument("args", nargs=-1)
@new_optgroup("Workload settings")
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
    help=f"""The Beaker workspace to pull experiments from. {config.get_help_string_for_default('workspace')}""",
    default=config.workspace,
)
@optgroup.option(
    "-b",
    "--budget",
    type=str,
    help=f"""The budget account to associate with the experiment. {config.get_help_string_for_default('budget')}""",
    default=config.budget,
)
@optgroup.option(
    "--group",
    "group_names",
    type=str,
    multiple=True,
    default=None,
    help="""A group to assign the experiment to. Multiple allowed.""",
)
@new_optgroup("Launch settings")
@optgroup.option(
    "--show-logs/--no-logs",
    default=None,
    help="""Whether or not to stream the logs to stdout as the experiment runs.""",
)
@optgroup.option(
    "--timeout",
    "timeout_str",
    type=str,
    default=None,
    help="""Time to wait (in seconds, by default) for the experiment to finish.
    Can also be specified as a duration such as '5m', '2h', etc.
    A timeout of -1 means wait indefinitely.
    A timeout of 0 means don't wait at all.
    This defaults to 0 unless you set --show-logs, in which case it defaults to -1.""",
    show_default=True,
)
@optgroup.option(
    "--start-timeout",
    "start_timeout_str",
    type=str,
    default=None,
    help="""Time to wait (in seconds, by default) for the experiment to start.
    Can also be specified as a duration such as '5m', '2h', etc.
    The experiment will be canceled if it doesn't start within this time.""",
)
@optgroup.option(
    "--inactive-timeout",
    "inactive_timeout_str",
    type=str,
    default=None,
    help="""Time to wait (in seconds, by default) for new log events when streaming logs.
    Can also be specified as a duration such as '5m', '2h', etc.
    The experiment will be canceled if no new logs are received within this time.""",
)
@optgroup.option(
    "--inactive-soft-timeout",
    "inactive_soft_timeout_str",
    type=str,
    default=None,
    help="""Time to wait (in seconds, by default) for new log events when streaming logs.
    Can also be specified as a duration such as '5m', '2h', etc.
    A warning notification will be issued if no new logs are received within this time.""",
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
    default=None,
)
@optgroup.option("--dry-run", is_flag=True, help="""Do a dry run only.""")
@optgroup.option(
    "--save-spec",
    type=click.Path(dir_okay=False, file_okay=True),
    help="""A path to save the generated YAML Beaker experiment spec to.""",
)
@new_optgroup(
    "Callbacks",
    "Callbacks provide a way to hook into events from gantry's launch loop. "
    "See https://github.com/allenai/beaker-gantry/blob/main/gantry/callbacks/slack.py for an example.",
)
@optgroup.option(
    "--callback-module",
    "callback_modules",
    type=str,
    multiple=True,
    help=f"""A module to import where custom callbacks are defined/registered. Multiple allowed.
    {config.get_help_string_for_default('callback_modules')}""",
    default=config.callback_modules,
)
@optgroup.option(
    "--callback",
    "callback_configs",
    type=str,
    multiple=True,
    help="""A callback name or JSON/YAML config to use. Multiple allowed. Note that callbacks are only
    used when following a workload locally (e.g. with '--show-logs' or '--timeout=-1').""",
)
@optgroup.option(
    "--slack-webhook-url",
    type=str,
    help="""A Slack webhook URL to send updates to. This is just a shortcut for configuring the 'slack' callback.""",
    envvar="GANTRY_SLACK_WEBHOOK_URL",
)
@new_optgroup("Constraints")
@optgroup.option(
    "-c",
    "--cluster",
    "clusters",
    type=str,
    multiple=True,
    default=None,
    help="""The name of a cluster to use or a glob pattern, e.g. --cluster='ai2/*-cirrascale'.
    Multiple allowed.
    If you don't specify a cluster or the priority, the priority will default to 'preemptible' and
    the job will be able to run on any on-premise cluster.""",
    show_default=True,
)
@optgroup.option(
    "--gpu-type",
    "gpu_types",
    type=str,
    multiple=True,
    default=None,
    help="""Filter clusters by GPU type (e.g. "--gpu-type=h100").
    Multiple allowed.""",
    show_default=True,
)
@optgroup.option(
    "--interconnect",
    type=click.Choice(["ib", "tcpxo"]),
    help="""Filter clusters by the type of interconnect they have, e.g. 'ib' for InfiniBand.""",
    default=None,
)
@optgroup.option(
    "--tag",
    "tags",
    type=str,
    multiple=True,
    default=None,
    help="""Filter clusters by a tag (e.g. "--tag=storage:weka").
    Multiple allowed, in which case only clusters that have all specified tags will be used.""",
)
@optgroup.option(
    "--hostname",
    "hostnames",
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
    help="""The number of logical CPU cores (e.g. 4.0, 0.5) to assign to each task replica.""",
)
@optgroup.option(
    "--gpus",
    type=int,
    help="""The number of GPUs (e.g. 1) to assign to each task replica.""",
)
@optgroup.option(
    "--memory",
    type=str,
    help="""The amount of system memory to assign to each task replica.
    This should be specified as a number with unit suffix (e.g. 2.5GiB).""",
)
@optgroup.option(
    "--shared-memory",
    type=str,
    help="""The size of /dev/shm as a number with unit suffix (e.g. 2.5GiB).""",
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
    "datasets",
    type=str,
    multiple=True,
    help="""An input dataset in the form of 'dataset-name:/mount/location' or
    'dataset-name:sub/path:/mount/location' to attach to your experiment.
    You can specify this option more than once to attach multiple datasets.""",
)
@optgroup.option(
    "-m",
    "--mount",
    "mounts",
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
    e.g. '--weka=oe-training-default:/data'. Multiple allowed.""",
)
@optgroup.option(
    "-u",
    "--upload",
    "uploads",
    type=str,
    multiple=True,
    help="""A local file or directory to upload and mount to the Beaker experiment in the form of
    '/local/path:/mounting/directory'.
    Multiple allowed.
    Note it only makes sense to use this for files that aren't committed to your repository.""",
)
@optgroup.option(
    "--env",
    "env_vars",
    type=str,
    help="""Environment variables to add the Beaker experiment.
    Should be in the form '{NAME}={VALUE}', or just '{NAME}' to take the value from a local environment
    variable of that name.""",
    multiple=True,
)
@optgroup.option(
    "--env-secret",
    "--secret-env",
    "env_secrets",
    type=str,
    help="""Environment variables to add to the Beaker experiment from Beaker secrets.
    Should be in the form '{NAME}={SECRET_NAME}', or just '{NAME}' to take the value from either
    (1) a Beaker secret in the workspace with the same name, or (2) a local
    environment variable of that name, in which case a new Beaker secret is created.""",
    multiple=True,
)
@optgroup.option(
    "--dataset-secret",
    "dataset_secrets",
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
    help=f"""The name of the Beaker secret that contains your GitHub token.
    {config.get_help_string_for_default('gh_token_secret', constants.GITHUB_TOKEN_SECRET)}""",
    default=config.gh_token_secret or constants.GITHUB_TOKEN_SECRET,
)
@optgroup.option(
    "--aws-config-secret",
    type=str,
    help="""The name of a Beaker secret that contains an AWS config file.""",
)
@optgroup.option(
    "--aws-credentials-secret",
    type=str,
    help="""The name of a Beaker secret that contains an AWS credentials file.""",
)
@optgroup.option(
    "--google-credentials-secret",
    type=str,
    help="""The name of a Beaker secret that contains a Google Cloud credentials JSON file
    for a service account.""",
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
@new_optgroup("Multi-node config")
@optgroup.option(
    "--replicas",
    type=int,
    help="""The number of task replicas to run.""",
)
@optgroup.option(
    "--leader-selection/--no-leader-selection",
    is_flag=True,
    help="""Specifies that the first task replica should be the leader and populates each task
    with 'BEAKER_LEADER_REPLICA_HOSTNAME' and 'BEAKER_LEADER_REPLICA_NODE_ID' environment variables.
    This is only applicable when '--replicas INT' and '--host-networking' are used,
    although the '--host-networking' flag can be omitted in this case since it's assumed.""",
    default=None,
)
@optgroup.option(
    "--host-networking/--no-host-networking",
    is_flag=True,
    help="""Specifies that each task replica should use the host's network.
    When used with '--replicas INT', this allows the replicas to communicate with each
    other using their hostnames.""",
    default=None,
)
@optgroup.option(
    "--propagate-failure/--no-propagate-failure",
    is_flag=True,
    help="""Stop the experiment if any task fails.""",
    default=None,
)
@optgroup.option(
    "--propagate-preemption/--no-propagate-preemption",
    is_flag=True,
    help="""Stop the experiment if any task is preempted.""",
    default=None,
)
@optgroup.option(
    "--synchronized-start-timeout",
    type=str,
    help="""
    If set, jobs in the replicated task will wait this long to start until all other jobs are also ready.
    This should be specified as a duration such as '5m', '30s', etc.
    """,
)
@optgroup.option(
    "--skip-tcpxo-setup",
    is_flag=True,
    help="""By default Gantry will configure NCCL for TCPXO when running a multi-node job on Augusta
    (--replicas > 1), but you can use this flag to skip that step if you need a custom configuration.
    If you do use this flag, you'll probably need to follow all of the steps documented here:

    https://beaker-docs.allen.ai/compute/augusta.html#distributed-workloads""",
    hidden=True,  # deprecated in favor of '--skip-nccl-setup'
)
@optgroup.option(
    "--skip-nccl-setup",
    is_flag=True,
    help="""By default Gantry will attempt to configure NCCL in an optimal way for the given hardware,
    but you can use this flag to skip that step if you need a custom configuration.
    If you do use this flag, you'll probably need to follow all of the steps documented here:

    https://beaker-docs.allen.ai/compute/augusta.html#distributed-workloads""",
)
@new_optgroup("Runtime")
@optgroup.option(
    "--runtime-dir",
    type=str,
    default=constants.RUNTIME_DIR,
    help="""The runtime directory on the image.""",
    show_default=True,
)
@optgroup.option(
    "--exec-method",
    type=click.Choice(["exec", "bash"]),
    default="exec",
    help="""Defines how your command+arguments are evaluated and executed at runtime.
    'exec' means gantry will call 'exec "$@"' to execute your command.
    'bash' means gantry will call 'bash -c "$*"' to execute your command.
    One reason you might prefer 'bash' over 'exec' is if you have shell variables in your arguments that
    you want expanded at runtime.""",
    show_default=True,
)
@optgroup.option(
    "--torchrun",
    is_flag=True,
    help="""Launch the given command with torchrun. This is just a shortcut for configuring your command
    with torchrun manually.

    When this flag is used with '--replicas INT', the '--leader-selection' flag is assumed (and not necessary),
    and gantry will automatically configure torchrun to use all GPUs across all replicas.
    Additionally '--propagate-failure' and '--propagate-preemption' are assumed, and '--synchronized-start-timeout'
    will default to '5m'.

    If don't want torchrun to communicate with replicas, you can use '--no-leader-selection'.""",
)
@new_optgroup("Setup hooks")
@optgroup.option(
    "--pre-setup",
    type=str,
    help="""Set a custom command or shell script to run before gantry's setup steps.""",
)
@optgroup.option(
    "--post-setup",
    type=str,
    help="""Set a custom command or shell script to run after gantry's setup steps.""",
)
@new_optgroup("Python settings")
@optgroup.option(
    "--python-manager",
    type=click.Choice(["uv", "conda"]),
    help="""The tool to use to manage Python installations and environments at runtime.
    If not specified this will default to 'uv' (recommended) in most cases, unless other '--conda-*' specific options
    are given (see below).""",
)
@optgroup.option(
    "--default-python-version",
    type=str,
    default=utils.get_local_python_version(),
    help="""The default Python version to use when constructing a new Python environment.
    This will be ignored if gantry is instructed to use an existing Python distribution/environment
    on the image, such as with the --system-python flag, the --uv-venv option, or the --conda-env option.""",
    show_default=True,
)
@optgroup.option(
    "--system-python",
    is_flag=True,
    help="""If set, gantry will try to use the default Python installation on the image.
    Though the behavior is a little different when using conda as the Python manager, in which
    case gantry will try to use the base conda environment.""",
)
@optgroup.option(
    "--install",
    type=str,
    help="""Override the default Python project installation method with a custom command or shell script,
    e.g. '--install "python setup.py install"' or '--install "my-custom-install-script.sh"'.""",
)
@optgroup.option(
    "--no-python",
    is_flag=True,
    help="""If set, gantry will skip setting up a Python environment altogether.
    This can be useful if your experiment doesn't need Python or if your image
    already contains a complete Python environment.""",
)
@new_optgroup(
    "Python uv settings",
    "Settings specific to the uv Python manager (--python-manager=uv).",
)
@optgroup.option(
    "--uv-venv",
    type=str,
    help="""A path to a Python virtual environment on the image.""",
)
@optgroup.option(
    "--uv-extra",
    "uv_extras",
    type=str,
    multiple=True,
    help="""Include optional dependencies for your local project from the specified extra name.
    Can be specified multiple times.
    If not provided, all extras will be installed unless --uv-no-extras is given.""",
)
@optgroup.option(
    "--uv-all-extras/--uv-no-extras",
    is_flag=True,
    help="""Install your local project with all extra dependencies, or no extra dependencies.
    This defaults to true unless --uv-extra is specified.""",
    default=None,
)
@optgroup.option(
    "--uv-torch-backend",
    type=str,
    help="""The backend to use when installing packages in the PyTorch ecosystem with uv.
    Valid options are 'auto', 'cpu', 'cu128', etc.""",
)
@new_optgroup(
    "Python conda settings",
    "Settings specific to the conda Python manager (--python-manager=conda).",
)
@optgroup.option(
    "--conda-file",
    type=click.Path(exists=True, dir_okay=False),
    help="""Path to a conda environment file for reconstructing your Python environment.
    If not specified, an 'environment.yml'/'environment.yaml' file will be used if it exists.""",
)
@optgroup.option(
    "--conda-env",
    type=str,
    help="""The name or path to an existing conda environment on the image to use.""",
)
def run(
    args,
    show_logs: bool | None = None,
    timeout_str: str | None = None,
    start_timeout_str: str | None = None,
    inactive_timeout_str: str | None = None,
    inactive_soft_timeout_str: str | None = None,
    dry_run: bool = False,
    callback_modules: Sequence[str] | None = None,
    callback_configs: Sequence[str] | None = None,
    slack_webhook_url: str | None = None,
    **kwargs,
):
    """
    Run a workload on Beaker.

    Example:

    $ gantry run --yes --show-logs -- python -c 'print("Hello, World!")'
    """
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

    # Parse timeouts.
    # NOTE: `timeout_str` has to be handled specially because of the '-1' value.
    timeout: int | None = None
    if timeout_str is not None:
        try:
            timeout = int(timeout_str)
        except ValueError:
            timeout = int(utils.parse_timedelta(timeout_str).total_seconds())

    start_timeout = (
        None
        if start_timeout_str is None
        else int(utils.parse_timedelta(start_timeout_str).total_seconds())
    )

    inactive_timeout = (
        None
        if inactive_timeout_str is None
        else int(utils.parse_timedelta(inactive_timeout_str).total_seconds())
    )

    inactive_soft_timeout = (
        None
        if inactive_soft_timeout_str is None
        else int(utils.parse_timedelta(inactive_soft_timeout_str).total_seconds())
    )

    # Import registered callback modules.
    callback_names = set(Callback.get_registered_names())
    for callback_module in callback_modules or []:
        utils.import_module(callback_module)
        for name in Callback.get_registered_names():
            if name not in callback_names:
                log.debug(f"Imported callback '{name}' from module '{callback_module}'.")
                callback_names.add(name)

    # Initialize callbacks.
    callbacks: list[Callback] = []
    has_slack_callback = False
    for callback_config_str in callback_configs or []:
        callback: Callback
        if "{" not in callback_config_str and "}" not in callback_config_str:
            try:
                callback_cls = Callback.get_registered_class(callback_config_str)
            except KeyError:
                raise ConfigurationError(f"Unknown callback name '{callback_config_str}'")

            try:
                callback = callback_cls()
            except TypeError as e:
                raise ConfigurationError(
                    f"Failed to initialize '{callback_config_str}' callback. If the callback has "
                    f"required arguments, you'll need to specify the callback as a JSON/YAML config.\n"
                    f"For example: --callback '{{type: {callback_config_str}, arg1: value1}}'."
                ) from e
        else:
            import yaml

            try:
                callback_json_config = yaml.safe_load(callback_config_str)
            except yaml.error.YAMLError as e:
                raise ConfigurationError(f"Invalid callback config: '{callback_config_str}'") from e

            try:
                callback = decode(Callback, callback_json_config)
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to decode callback from '{callback_config_str}'"
                ) from e

        callbacks.append(callback)
        log.debug("Initialized callback: %s", callback)
        if isinstance(callback, SlackCallback):
            has_slack_callback = True

    if slack_webhook_url is not None and not has_slack_callback:
        callbacks.append(SlackCallback(webhook_url=slack_webhook_url))

    recipe = Recipe(args=args, callbacks=callbacks, **kwargs)
    if dry_run:
        recipe.dry_run()
    else:
        recipe.launch(
            show_logs=show_logs,
            timeout=timeout,
            start_timeout=start_timeout,
            inactive_timeout=inactive_timeout,
            inactive_soft_timeout=inactive_soft_timeout,
            auto_cancel=True,
        )
