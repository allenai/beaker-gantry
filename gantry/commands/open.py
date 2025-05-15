import click
from beaker.exceptions import BeakerNotFoundError
from rich import print

from .. import util
from ..exceptions import NotFoundError
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(name="open", **CLICK_COMMAND_DEFAULTS)
@click.argument(
    "identifiers",
    nargs=-1,
    type=str,
)
def open_cmd(identifiers: tuple[str, ...] = tuple()):
    """
    Open the page for a Beaker object in your browser.
    """
    with util.init_client(ensure_workspace=False) as beaker:
        for identifier in identifiers:
            try:
                url = beaker.workload.url(beaker.workload.get(identifier))
                print(f"Resolved workload '{identifier}' to {url}")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.workspace.url(beaker.workspace.get(identifier))
                print(f"Resolved workspace '{identifier}' to {url}")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.cluster.url(beaker.cluster.get(identifier))
                print(f"Resolved cluster '{identifier}' to {url}")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.image.url(beaker.image.get(identifier))
                print(f"Resolved image '{identifier}' to {url}")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.dataset.url(beaker.dataset.get(identifier))
                print(f"Resolved dataset '{identifier}' to {url}")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = util.group_url(beaker, beaker.group.get(identifier))
                print(f"Resolved group '{identifier}' to {url}")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            raise NotFoundError(f"Beaker resource '{identifier}' not found or does not have a URL")
