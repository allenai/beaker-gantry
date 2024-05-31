import click
from beaker import Beaker

from .. import util
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("experiment", nargs=1, required=True, type=str)
@click.option(
    "-t", "--tail", is_flag=True, help="Only tail the logs as opposed to printing all logs so far."
)
def follow(experiment: str, tail: bool = False):
    """
    Follow the logs for a running experiment.
    """
    beaker = Beaker.from_env(session=True)
    exp = beaker.experiment.get(experiment)
    job = util.follow_experiment(beaker, exp, tail=tail)
    util.display_results(beaker, exp, job)
