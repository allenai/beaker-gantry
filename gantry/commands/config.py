import click

from .. import beaker_utils, constants, utils
from ..config import get_global_config
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
    help=f"""The Beaker workspace to set the secret in. {get_global_config().get_help_string_for_default('workspace')}""",
    default=get_global_config().workspace,
)
@click.option(
    "-s",
    "--secret",
    type=str,
    help=f"""The name of the Beaker secret to write to.
    {get_global_config().get_help_string_for_default('gh_token_secret', constants.GITHUB_TOKEN_SECRET)}""",
    default=get_global_config().gh_token_secret or constants.GITHUB_TOKEN_SECRET,
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="""Skip all confirmation prompts.""",
)
def set_gh_token(
    token: str,
    workspace: str | None = None,
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
    with beaker_utils.init_client(workspace=workspace, yes=yes) as beaker:
        # Write token to secret.
        beaker.secret.write(secret, token)

        utils.print_stdout(
            f"[green]\N{check mark} GitHub token added to workspace "
            f"'{beaker.config.default_workspace}' as the secret '{secret}'"
        )
