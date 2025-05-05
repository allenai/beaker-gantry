import subprocess
from pathlib import Path

import pytest
from beaker import BeakerExperimentSpec, BeakerJobPriority
from beaker.common import to_nanoseconds


def _build_run_cmd(
    *,
    workspace_name: str,
    run_name: str,
    spec_path: Path,
    options: list[str] | None = None,
    command: list[str] | None = None,
) -> list[str]:
    command = command or ["python", "-c", "print('Hello, World!')"]
    return [
        "gantry",
        "run",
        "--dry-run",
        "--allow-dirty",
        "--save-spec",
        str(spec_path),
        "--name",
        run_name,
        "--workspace",
        workspace_name,
        "--yes",
        *(options or []),
        "--",
        *command,
    ]


def test_dry_run(workspace_name: str, run_name: str, tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    result = subprocess.run(
        _build_run_cmd(
            workspace_name=workspace_name,
            run_name=run_name,
            spec_path=spec_path,
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Make sure spec is valid.
    spec = BeakerExperimentSpec.from_file(spec_path)
    # Should be preemptible since we didn't specify a cluster.
    assert spec.tasks[0].context.preemptible is True


def test_dry_run_not_preemptible(workspace_name: str, run_name: str, tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    result = subprocess.run(
        _build_run_cmd(
            workspace_name=workspace_name,
            run_name=run_name,
            spec_path=spec_path,
            options=["--not-preemptible"],
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Make sure spec is valid.
    spec = BeakerExperimentSpec.from_file(spec_path)
    # Should be preemptible since we didn't specify a cluster.
    assert spec.tasks[0].context.preemptible is False


def test_dry_run_with_cluster(
    workspace_name: str, run_name: str, tmp_path: Path, cluster_name: str, second_cluster_name: str
):
    spec_path = tmp_path / "spec.yaml"
    result = subprocess.run(
        _build_run_cmd(
            workspace_name=workspace_name,
            run_name=run_name,
            spec_path=spec_path,
            options=["--cluster", cluster_name, "--cluster", second_cluster_name],
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Make sure spec is valid.
    spec = BeakerExperimentSpec.from_file(spec_path)
    assert spec.tasks[0].context.preemptible is None
    assert spec.tasks[0].constraints is not None
    assert spec.tasks[0].constraints.cluster is not None
    assert set(spec.tasks[0].constraints.cluster) == set([cluster_name, second_cluster_name])


def test_dry_run_with_budget(workspace_name: str, run_name: str, tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    result = subprocess.run(
        _build_run_cmd(
            workspace_name=workspace_name,
            run_name=run_name,
            spec_path=spec_path,
            options=["--budget", "ai2/allennlp"],
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Make sure spec is valid.
    spec = BeakerExperimentSpec.from_file(spec_path)
    assert spec.budget == "ai2/allennlp"


@pytest.mark.parametrize("timeout", ["10m", "1m30s"])
def test_dry_run_with_task_timeouts(
    workspace_name: str, run_name: str, tmp_path: Path, timeout: str
):
    spec_path = tmp_path / "spec.yaml"
    result = subprocess.run(
        _build_run_cmd(
            workspace_name=workspace_name,
            run_name=run_name,
            spec_path=spec_path,
            options=["--task-timeout", timeout, "--synchronized-start-timeout", timeout],
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Make sure spec is valid.
    spec = BeakerExperimentSpec.from_file(spec_path)
    assert isinstance(spec.tasks[0].timeout, int)
    assert isinstance(spec.tasks[0].synchronized_start_timeout, int)
    assert spec.tasks[0].timeout == to_nanoseconds(timeout)
    assert spec.tasks[0].synchronized_start_timeout == to_nanoseconds(timeout)


@pytest.mark.parametrize("priority", ["low", "normal"])
def test_dry_run_with_priority(workspace_name: str, run_name: str, tmp_path: Path, priority: str):
    spec_path = tmp_path / "spec.yaml"
    result = subprocess.run(
        _build_run_cmd(
            workspace_name=workspace_name,
            run_name=run_name,
            spec_path=spec_path,
            options=["--priority", priority],
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Make sure spec is valid.
    spec = BeakerExperimentSpec.from_file(spec_path)
    assert BeakerJobPriority.from_any(spec.tasks[0].context.priority) == BeakerJobPriority.from_any(
        priority
    )


def test_dry_run_with_replicas(workspace_name: str, run_name: str, tmp_path: Path):
    spec_path = tmp_path / "spec.yaml"
    result = subprocess.run(
        _build_run_cmd(
            workspace_name=workspace_name,
            run_name=run_name,
            spec_path=spec_path,
            options=[
                "--gpus",
                "8",
                "--host-networking",
                "--leader-selection",
                "--propagate-failure",
                "--propagate-preemption",
                "--replicas",
                "4",
            ],
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Make sure spec is valid.
    spec = BeakerExperimentSpec.from_file(spec_path)
    assert spec.tasks[0].resources is not None
    assert spec.tasks[0].resources.gpu_count == 8
    assert spec.tasks[0].host_networking is True
    assert spec.tasks[0].leader_selection is True
    assert spec.tasks[0].propagate_failure is True
    assert spec.tasks[0].propagate_preemption is True
    assert spec.tasks[0].replicas == 4
