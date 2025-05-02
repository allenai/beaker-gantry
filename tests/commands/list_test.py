import subprocess


def test_list_command(workspace_name: str, user_name: str):
    result = subprocess.run(
        ["gantry", "list", "--author", user_name, "--workspace", workspace_name, "--limit", "2"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
