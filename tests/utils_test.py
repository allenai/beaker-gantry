import pytest

from gantry.utils import format_timedelta, highlight_pattern, parse_timedelta


@pytest.mark.parametrize(
    "s, pattern, result",
    [
        ("NVIDIA A100 80GB", "A", "NVIDI[b green]A[/] [b green]A[/]100 80GB"),
        ("NVIDIA A100 80GB", "A100", "NVIDIA [b green]A100[/] 80GB"),
    ],
)
def test_highlight_pattern(s: str, pattern: str, result: str):
    assert highlight_pattern(s, pattern) == result


@pytest.mark.parametrize(
    "s_in, s_out",
    [
        ("2m 30s", "2 minutes, 30 seconds"),
        ("2m30s", "2 minutes, 30 seconds"),
        ("2min30sec", "2 minutes, 30 seconds"),
        ("30", "30 seconds"),
        ("0", "under 1 second"),
    ],
)
def test_parse_and_format_timedelta(s_in: str, s_out: str):
    assert format_timedelta(parse_timedelta(s_in)) == s_out
