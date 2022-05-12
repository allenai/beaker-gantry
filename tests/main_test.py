import subprocess

from gantry.version import VERSION


def test_help():
    result = subprocess.run(["gantry", "--help"])
    assert result.returncode == 0


def test_version():
    result = subprocess.run(["gantry", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert VERSION in result.stdout


def test_dry_run(workspace_name: str, beaker_cluster_name: str, run_name: str):
    result = subprocess.run(
        [
            "gantry",
            "run",
            "--dry-run",
            "--allow-dirty",
            "--name",
            run_name,
            "--workspace",
            workspace_name,
            "--cluster",
            beaker_cluster_name,
            "--",
            "python",
            "-c",
            "print('Hello, World!')",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Dry run experiment spec" in result.stdout
