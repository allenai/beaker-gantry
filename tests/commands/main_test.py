import subprocess

from gantry.version import VERSION


def test_help():
    result = subprocess.run(["gantry", "--help"])
    assert result.returncode == 0


def test_version():
    result = subprocess.run(["gantry", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert VERSION in result.stdout
