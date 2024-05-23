import click
from beaker import Beaker

from .. import util
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(**CLICK_COMMAND_DEFAULTS)
@click.argument("experiment", nargs=1, required=True, type=str)
def follow(experiment: str):
    """
    Follow the logs for a running experiment.
    """
    beaker = Beaker.from_env(session=True)
    beaker.experiment.follow
    exp = beaker.experiment.get(experiment)
    job = util.follow_experiment(beaker, exp)
    util.display_results(beaker, exp, job)
