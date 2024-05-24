from typing import Optional

import click
from rich import print

from .. import constants, util
from .main import CLICK_COMMAND_DEFAULTS, CLICK_GROUP_DEFAULTS, main


@main.group(**CLICK_GROUP_DEFAULTS)
def config():
    """
    Configure Gantry for a specific Beaker workspace.
    """


@config.command(**CLICK_COMMAND_DEFAULTS)  # type: ignore
@click.argument("token")
@click.option(
    "-w",
    "--workspace",
    type=str,
    help="""The Beaker workspace to use.
    If not specified, your default workspace will be used.""",
)
@click.option(
    "-s",
    "--secret",
    type=str,
    help="""The name of the Beaker secret to write to.""",
    default=constants.GITHUB_TOKEN_SECRET,
    show_default=True,
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="""Skip all confirmation prompts.""",
)
def set_gh_token(
    token: str,
    workspace: Optional[str] = None,
    secret: str = constants.GITHUB_TOKEN_SECRET,
    yes: bool = False,
):
    """
    Set or update Gantry's GitHub token for the workspace.

    You can create a suitable GitHub token by going to https://github.com/settings/tokens/new
    and generating a token with the '\N{ballot box with check} repo' scope.

    Example:

    $ gantry config set-gh-token "$GITHUB_TOKEN"
    """
    # Initialize Beaker client and validate workspace.
    beaker = util.ensure_workspace(workspace=workspace, yes=yes, gh_token_secret=secret)

    # Write token to secret.
    beaker.secret.write(secret, token)

    print(
        f"[green]\N{check mark} GitHub token added to workspace "
        f"'{beaker.config.default_workspace}' as the secret '{secret}'"
    )
