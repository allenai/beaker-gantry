import click
from beaker.exceptions import BeakerNotFoundError

from .. import beaker_utils, utils
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
    with beaker_utils.init_client(ensure_workspace=False) as beaker:
        for identifier in identifiers:
            try:
                url = beaker.workload.url(beaker.workload.get(identifier))
                utils.print_stdout(f"Resolved workload [cyan]{identifier}[/] to [blue u]{url}[/]")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.workspace.url(beaker.workspace.get(identifier))
                utils.print_stdout(f"Resolved workspace [cyan]{identifier}[/] to [blue u]{url}[/]")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.cluster.url(beaker.cluster.get(identifier))
                utils.print_stdout(f"Resolved cluster [cyan]{identifier}[/] to [blue u]{url}[/]")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.image.url(beaker.image.get(identifier))
                utils.print_stdout(f"Resolved image [cyan]{identifier}[/] to [blue u]{url}[/]")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker.dataset.url(beaker.dataset.get(identifier))
                utils.print_stdout(f"Resolved dataset [cyan]{identifier}[/] to [blue u]{url}[/]")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            try:
                url = beaker_utils.group_url(beaker, beaker.group.get(identifier))
                utils.print_stdout(f"Resolved group [cyan]{identifier}[/] to [blue u]{url}[/]")
                click.launch(url)
                continue
            except BeakerNotFoundError:
                pass

            raise NotFoundError(f"Beaker resource '{identifier}' not found or does not have a URL")
