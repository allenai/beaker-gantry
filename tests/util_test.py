import pytest

from gantry.util import highlight_pattern


@pytest.mark.parametrize(
    "s, pattern, result",
    [
        ("NVIDIA A100 80GB", "A", "NVIDI[b green]A[/] [b green]A[/]100 80GB"),
        ("NVIDIA A100 80GB", "A100", "NVIDIA [b green]A100[/] 80GB"),
    ],
)
def test_highlight_pattern(s: str, pattern: str, result: str):
    assert highlight_pattern(s, pattern) == result
