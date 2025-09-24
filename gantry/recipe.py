import dataclasses
from dataclasses import dataclass
from typing import Literal, Sequence

from beaker import BeakerWorkload

from . import constants, utils
from .aliases import PathOrStr
from .launch import launch_experiment


@dataclass
class Recipe:
    """
    A recipe defines how Gantry creates a Beaker workload.
    """

    args: Sequence[str]
    name: str | None = None
    description: str | None = None
    task_name: str = "main"
    workspace: str | None = None
    group_names: Sequence[str] | None = None
    clusters: Sequence[str] | None = None
    gpu_types: Sequence[str] | None = None
    tags: Sequence[str] | None = None
    hostnames: Sequence[str] | None = None
    beaker_image: str | None = None
    docker_image: str | None = None
    cpus: float | None = None
    gpus: int | None = None
    memory: str | None = None
    shared_memory: str | None = None
    datasets: Sequence[str] | None = None
    gh_token_secret: str = constants.GITHUB_TOKEN_SECRET
    ref: str | None = None
    branch: str | None = None
    conda_file: PathOrStr | None = None
    conda_env: str | None = None
    python_manager: Literal["uv", "conda"] | None = None
    system_python: bool = False
    uv_venv: str | None = None
    uv_extras: Sequence[str] | None = None
    uv_all_extras: bool | None = None
    uv_torch_backend: str | None = None
    env_vars: Sequence[str] | None = None
    env_secrets: Sequence[str] | None = None
    dataset_secrets: Sequence[str] | None = None
    task_timeout: str | None = None
    allow_dirty: bool = False
    yes: bool | None = None
    save_spec: PathOrStr | None = None
    priority: str | None = None
    install: str | None = None
    no_python: bool = False
    replicas: int | None = None
    leader_selection: bool = False
    host_networking: bool = False
    propagate_failure: bool | None = None
    propagate_preemption: bool | None = None
    synchronized_start_timeout: str | None = None
    mounts: Sequence[str] | None = None
    weka: str | None = None
    budget: str | None = None
    preemptible: bool | None = None
    retries: int | None = None
    results: str = constants.RESULTS_DIR
    runtime_dir: str = constants.RUNTIME_DIR
    exec_method: Literal["exec", "bash"] = "exec"
    skip_tcpxo_setup: bool = False
    default_python_version: str = utils.get_local_python_version()
    pre_setup: str | None = None
    post_setup: str | None = None
    slack_webhook_url: str | None = None

    def dry_run(self) -> None:
        """
        Do a dry-run to validate options.
        """
        kwargs = dataclasses.asdict(self)
        launch_experiment(**kwargs, dry_run=True)

    def launch(self, show_logs: bool | None = None, timeout: int | None = None) -> BeakerWorkload:
        """
        Launch an experiment on Beaker. Same as the ``gantry run`` command.

        :returns: The Beaker workload.
        """
        kwargs = dataclasses.asdict(self)
        workload = launch_experiment(**kwargs, show_logs=show_logs, timeout=timeout)
        assert workload is not None
        return workload
