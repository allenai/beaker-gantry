import dataclasses
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from beaker import Beaker, BeakerWorkload

from . import constants, utils
from .aliases import PathOrStr
from .callbacks import Callback
from .exceptions import *
from .git_utils import GitRepoState
from .launch import launch_experiment


@dataclass
class Recipe:
    """
    A recipe defines how Gantry creates a Beaker workload and can be used to programmatically
    launch Gantry runs from Python as opposed to from the command-line.
    """

    # Workload settings
    args: Sequence[str]
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    budget: str | None = None
    group_names: Sequence[str] | None = None

    # Launch settings.
    allow_dirty: bool = False
    yes: bool | None = None
    save_spec: PathOrStr | None = None

    # Callbacks.
    callbacks: Sequence[Callback] | None = None

    # Constraints.
    clusters: Sequence[str] | None = None
    gpu_types: Sequence[str] | None = None
    interconnect: Literal["ib", "tcpxo"] | None = None
    tags: Sequence[str] | None = None
    hostnames: Sequence[str] | None = None

    # Resources.
    cpus: float | None = None
    gpus: int | None = None
    memory: str | None = None
    shared_memory: str | None = None

    # Inputs.
    beaker_image: str | None = None
    docker_image: str | None = None
    datasets: Sequence[str] | None = None
    env_vars: Sequence[str | tuple[str, str]] | None = None
    env_secrets: Sequence[str | tuple[str, str]] | None = None
    dataset_secrets: Sequence[str | tuple[str, str]] | None = None
    mounts: Sequence[str | tuple[str, str]] | None = None
    weka: Sequence[str | tuple[str, str]] | None = None
    uploads: Sequence[str | tuple[str, str]] | None = None
    ref: str | None = None
    branch: str | None = None
    git_repo: GitRepoState | None = None
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET
    aws_config_secret: str | None = None
    aws_credentials_secret: str | None = None
    google_credentials_secret: str | None = None

    # Outputs.
    results: str = constants.RESULTS_DIR

    # Task settings.
    task_name: str = "main"
    priority: str | None = None
    task_timeout: str | None = None
    preemptible: bool | None = None
    retries: int | None = None

    # Multi-node config.
    replicas: int | None = None
    leader_selection: bool | None = None
    host_networking: bool | None = None
    propagate_failure: bool | None = None
    propagate_preemption: bool | None = None
    synchronized_start_timeout: str | None = None
    skip_tcpxo_setup: bool = dataclasses.field(default=False, repr=False)  # deprecated
    skip_nccl_setup: bool = False

    # Runtime.
    runtime_dir: str = constants.RUNTIME_DIR
    exec_method: Literal["exec", "bash"] = "exec"
    torchrun: bool = False

    # Setup hooks.
    pre_setup: str | None = None
    post_setup: str | None = None

    # Python settings.
    python_manager: Literal["uv", "conda"] | None = None
    default_python_version: str = utils.get_local_python_version()
    system_python: bool = False
    install: str | None = None
    no_python: bool = False

    # Python UV settings.
    uv_venv: str | None = None
    uv_extras: Sequence[str] | None = None
    uv_all_extras: bool | None = None
    uv_torch_backend: str | None = None

    # Python Conda settings.
    conda_file: PathOrStr | None = None
    conda_env: str | None = None

    @classmethod
    def multi_node_torchrun(
        cls,
        cmd: Sequence[str],
        gpus_per_node: int,
        num_nodes: int,
        shared_memory: str | None = "10GiB",
        **kwargs,
    ) -> "Recipe":
        """
        Create a multi-node recipe using torchrun.
        """
        return cls(
            args=cmd,
            gpus=gpus_per_node,
            replicas=num_nodes,
            shared_memory=shared_memory,
            torchrun=True,
            **kwargs,
        )

    def _get_launch_args(self) -> Sequence[str]:
        if isinstance(self.args, str):
            raise ConfigurationError("args must be a sequence of strings, not a single string")
        return self.args

    def _get_launch_kwargs(self) -> dict[str, Any]:
        kwargs = dataclasses.asdict(self)
        kwargs["callbacks"] = self.callbacks
        kwargs["git_repo"] = self.git_repo
        kwargs.pop("args")
        return kwargs

    def dry_run(self, client: Beaker | None = None) -> None:
        """
        Do a dry-run to validate options.
        """
        launch_experiment(
            self._get_launch_args(),
            **self._get_launch_kwargs(),
            client=client,
            dry_run=True,
        )

    def launch(
        self,
        show_logs: bool | None = None,
        timeout: int | None = None,
        start_timeout: int | None = None,
        inactive_timeout: int | None = None,
        inactive_soft_timeout: int | None = None,
        auto_cancel: bool = False,
        client: Beaker | None = None,
    ) -> BeakerWorkload:
        """
        Launch an experiment on Beaker. Same as the ``gantry run`` command.

        :returns: The Beaker workload.
        """
        workload = launch_experiment(
            self._get_launch_args(),
            **self._get_launch_kwargs(),
            show_logs=show_logs,
            timeout=timeout,
            start_timeout=start_timeout,
            inactive_timeout=inactive_timeout,
            inactive_soft_timeout=inactive_soft_timeout,
            auto_cancel=auto_cancel,
            client=client,
        )
        assert workload is not None
        return workload

    def with_replicas(
        self,
        replicas: int,
        leader_selection: bool = True,
        host_networking: bool = True,
        propagate_failure: bool = True,
        propagate_preemption: bool = True,
        synchronized_start_timeout: str = "5m",
        skip_nccl_setup: bool = False,
    ) -> "Recipe":
        """
        Add replicas to the recipe.
        """
        if replicas < 2:
            raise ConfigurationError("replicas must be at least 2")
        return dataclasses.replace(
            self,
            replicas=replicas,
            leader_selection=leader_selection,
            host_networking=host_networking,
            propagate_failure=propagate_failure,
            propagate_preemption=propagate_preemption,
            synchronized_start_timeout=synchronized_start_timeout,
            skip_nccl_setup=skip_nccl_setup,
        )
