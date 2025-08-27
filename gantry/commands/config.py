from typing import Optional

import click

from .. import constants, util
from ..util import print_stdout as print
from .main import CLICK_COMMAND_DEFAULTS, CLICK_GROUP_DEFAULTS
from .main import config as _config
from .main import main


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
    help=f"""The Beaker workspace to pull experiments from. {_config.get_help_string_for_default('workspace')}""",
    default=_config.workspace,
)
@click.option(
    "-s",
    "--secret",
    type=str,
    help=f"""The name of the Beaker secret to write to.
    {_config.get_help_string_for_default('gh_token_secret', constants.GITHUB_TOKEN_SECRET)}""",
    default=_config.gh_token_secret or constants.GITHUB_TOKEN_SECRET,
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
    with util.init_client(workspace=workspace, yes=yes) as beaker:
        # Write token to secret.
        beaker.secret.write(secret, token)

        print(
            f"[green]\N{check mark} GitHub token added to workspace "
            f"'{beaker.config.default_workspace}' as the secret '{secret}'"
        )
