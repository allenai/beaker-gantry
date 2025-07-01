import click
from beaker import BeakerJobPriority
from click_option_group import optgroup

from .. import constants
from ..api import launch_experiment
from ..exceptions import *
from .main import CLICK_COMMAND_DEFAULTS, main, new_optgroup


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
    "clusters",
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
    "--gpu-type",
    "gpu_types",
    type=str,
    multiple=True,
    default=None,
    help="""Launch on any cluster with this type of GPU (e.g. "h100"). Multiple allowed.""",
    show_default=True,
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
    e.g. --weka=oe-training-default:/data""",
)
@optgroup.option(
    "--env",
    "env_vars",
    type=str,
    help="""Environment variables to add the Beaker experiment. Should be in the form '{NAME}={VALUE}'.""",
    multiple=True,
)
@optgroup.option(
    "--env-secret",
    "--secret-env",
    "env_secrets",
    type=str,
    help="""Environment variables to add the Beaker experiment from Beaker secrets.
    Should be in the form '{NAME}={SECRET_NAME}'.""",
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
@new_optgroup("Multi-node config")
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
@optgroup.option(
    "--skip-tcpxo-setup",
    is_flag=True,
    help="""By default Gantry will configure NCCL for TCPXO when running multi-node job on Augusta,
    but you can use this flag to skip that step if you need a custom configuration.
    If you do use this flag, you'll probably need to follow all of the steps documented here:

    https://beaker-docs.allen.ai/compute/augusta.html#distributed-workloads""",
)
@new_optgroup("Python settings")
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
    "--python-version",
    type=str,
    help="""The default Python version to use when constructing a new Python environment (e.g. --python-version='3.12').
    This won't be applied if --venv is specified or a conda environment file is used.""",
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
    help="""Override the default Python installation method with a custom command or shell script,
    e.g. '--install "python setup.py install"' or '--install "my-custom-install-script.sh"'.""",
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
def run(*args, **kwargs):
    """
    Run an experiment on Beaker.

    Example:

    $ gantry run --yes --timeout=-1 -- python -c 'print("Hello, World!")'
    """
    launch_experiment(*args, **kwargs)
