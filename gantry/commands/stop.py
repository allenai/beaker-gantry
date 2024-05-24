import click
from beaker import Beaker
from rich import print

from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("experiment", nargs=1, required=True, type=str)
def stop(experiment: str):
    """
    Stop a running experiment.
    """
    beaker = Beaker.from_env(session=True)
    exp = beaker.experiment.get(experiment)
    beaker.experiment.stop(exp)
    print(f"[b green]\N{check mark}[/] [b cyan]{exp.name}[/] stopped")
