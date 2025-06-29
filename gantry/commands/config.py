from typing import Any, Optional

import click
from rich import print
from rich.console import Console
from rich.table import Table

from .. import config as gantry_config
from .. import constants, util
from .main import CLICK_COMMAND_DEFAULTS, CLICK_GROUP_DEFAULTS, main


@main.group(**CLICK_GROUP_DEFAULTS)
def config():
    """
    Configure Gantry settings and profiles.
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
    and generating a token with the '\N{BALLOT BOX WITH CHECK} repo' scope.

    Example:

    $ gantry config set-gh-token "$GITHUB_TOKEN"
    """
    # Initialize Beaker client and validate workspace.
    with util.init_client(workspace=workspace, yes=yes) as beaker:
        # Write token to secret.
        beaker.secret.write(secret, token)

        print(
            f"[green]\N{CHECK MARK} GitHub token added to workspace "
            f"'{beaker.config.default_workspace}' as the secret '{secret}'"
        )


@config.command("list-profiles", **CLICK_COMMAND_DEFAULTS)  # type: ignore
def list_profiles():
    """
    List all available configuration profiles.

    Example:

    $ gantry config list-profiles
    """
    try:
        cfg = gantry_config.load_config()
    except Exception:
        print("[yellow]No configuration file found. Run 'gantry config init' to create one.[/]")
        return

    table = Table(title="Gantry Configuration Profiles")
    table.add_column("Profile", style="cyan")
    table.add_column("Default", style="green")
    table.add_column("Settings", style="yellow")

    for profile_name in cfg.list_profiles():
        is_default = "✓" if profile_name == cfg.default_profile else ""
        profile = cfg.profiles[profile_name]

        # Count non-None settings
        settings_count = sum(1 for field in profile.__dataclass_fields__ if getattr(profile, field) is not None)

        table.add_row(profile_name, is_default, str(settings_count))

    console = Console()
    console.print(table)


@config.command(**CLICK_COMMAND_DEFAULTS)  # type: ignore
@click.argument("profile_name", required=False)
def show(profile_name: Optional[str] = None):
    """
    Show configuration for a specific profile or the default profile.

    Example:

    $ gantry config show

    $ gantry config show training
    """
    try:
        cfg = gantry_config.load_config()
    except Exception:
        print("[yellow]No configuration file found. Run 'gantry config init' to create one.[/]")
        return

    profile_name = profile_name or cfg.default_profile

    try:
        profile = cfg.get_profile(profile_name)
    except gantry_config.ConfigError as e:
        print(f"[red]Error: {e}[/]")
        return

    console = Console()
    console.print(f"\n[bold cyan]Profile: {profile_name}[/]\n")

    # Display configuration in a readable format
    config_dict = profile.to_dict()
    if not config_dict:
        console.print("[yellow]No settings configured for this profile.[/]")
    else:
        for key, value in config_dict.items():
            if isinstance(value, dict):
                console.print(f"[bold]{key}:[/]")
                for k, v in value.items():
                    console.print(f"  {k}: {v}")
            elif isinstance(value, list):
                console.print(f"[bold]{key}:[/] {', '.join(value)}")
            else:
                console.print(f"[bold]{key}:[/] {value}")


@config.command(**CLICK_COMMAND_DEFAULTS)  # type: ignore
@click.argument("setting", type=str)
@click.argument("value", type=str)
@click.option(
    "--profile",
    type=str,
    help="Profile to update. If not specified, updates the default profile.",
)
def set(setting: str, value: str, profile: Optional[str] = None):
    """
    Set a configuration value for a profile.

    Examples:

    $ gantry config set beaker_image ai2/conda

    $ gantry config set gpus 2 --profile training

    $ gantry config set env_vars "KEY=value"

    $ gantry config set weka "path1,path2,path3"
    """
    cfg = gantry_config.load_config()
    profile_name = profile or cfg.default_profile

    # Ensure profile exists
    if profile_name not in cfg.profiles:
        cfg.profiles[profile_name] = gantry_config.ProfileConfig()

    profile_config = cfg.profiles[profile_name]

    # Handle special cases for type conversion
    converted_value: Any = value
    if setting in ("gpus", "replicas", "timeout"):
        converted_value = int(value)
    elif setting in ("preemptible", "show_logs", "allow_dirty", "no_python", "no_conda"):
        converted_value = value.lower() in ("true", "yes", "1", "on")
    elif setting in ("env_vars", "datasets"):
        # These are dictionaries, expect format "key=value"
        if "=" not in value:
            print(f"[red]Error: {setting} must be in format 'key=value'[/]")
            return
        key, val = value.split("=", 1)
        current_dict = getattr(profile_config, setting, {})
        current_dict[key] = val
        converted_value = current_dict
    elif setting in ("weka",):
        # These are lists, expect comma-separated values
        converted_value = [item.strip() for item in value.split(",") if item.strip()]

    # Check if setting exists
    if not hasattr(profile_config, setting):
        print(f"[red]Error: Unknown setting '{setting}'[/]")
        print("[yellow]Available settings:[/]")
        for field_name in profile_config.__dataclass_fields__:
            print(f"  - {field_name}")
        return

    setattr(profile_config, setting, converted_value)
    cfg.save()

    print(f"[green]✓ Set {setting}={converted_value} for profile '{profile_name}'[/]")


@config.command(**CLICK_COMMAND_DEFAULTS)  # type: ignore
@click.argument("setting", type=str)
@click.option(
    "--profile",
    type=str,
    help="Profile to update. If not specified, updates the default profile.",
)
def unset(setting: str, profile: Optional[str] = None):
    """
    Remove a configuration value from a profile.

    Example:

    $ gantry config unset gpus --profile training
    """
    cfg = gantry_config.load_config()
    profile_name = profile or cfg.default_profile

    if profile_name not in cfg.profiles:
        print(f"[red]Error: Profile '{profile_name}' not found[/]")
        return

    profile_config = cfg.profiles[profile_name]

    if not hasattr(profile_config, setting):
        print(f"[red]Error: Unknown setting '{setting}'[/]")
        return

    # Reset to None (or empty dict/list for dict/list fields)
    if setting in ("env_vars", "datasets"):
        setattr(profile_config, setting, {})
    elif setting in ("weka",):
        setattr(profile_config, setting, [])
    else:
        setattr(profile_config, setting, None)

    cfg.save()
    print(f"[green]✓ Unset {setting} for profile '{profile_name}'[/]")


@config.command(**CLICK_COMMAND_DEFAULTS)  # type: ignore
def init():
    """
    Initialize a new configuration file with a default profile.

    Example:

    $ gantry config init
    """
    config_path = gantry_config.get_config_path()

    if config_path.exists():
        print(f"[yellow]Configuration file already exists at {config_path}[/]")
        if not click.confirm("Do you want to overwrite it?"):
            return

    cfg = gantry_config.GantryConfig(default_profile="default", profiles={"default": gantry_config.ProfileConfig()})

    cfg.save()
    print(f"[green]✓ Created configuration file at {config_path}[/]")
    print("[cyan]You can now use 'gantry config set' to configure your default settings.[/]")


@config.command("create-profile", **CLICK_COMMAND_DEFAULTS)  # type: ignore
@click.argument("profile_name", type=str)
def create_profile(profile_name: str):
    """
    Create a new configuration profile.

    Example:

    $ gantry config create-profile training
    """
    cfg = gantry_config.load_config()

    if profile_name in cfg.profiles:
        print(f"[red]Error: Profile '{profile_name}' already exists[/]")
        return

    cfg.profiles[profile_name] = gantry_config.ProfileConfig()
    cfg.save()

    print(f"[green]✓ Created profile '{profile_name}'[/]")
    print(f"[cyan]Use 'gantry config set <setting> <value> --profile {profile_name}' to configure it.[/]")


@config.command("set-default", **CLICK_COMMAND_DEFAULTS)  # type: ignore
@click.argument("profile_name", type=str)
def set_default(profile_name: str):
    """
    Set the default configuration profile.

    Example:

    $ gantry config set-default training
    """
    cfg = gantry_config.load_config()

    if profile_name not in cfg.profiles:
        print(f"[red]Error: Profile '{profile_name}' not found[/]")
        return

    cfg.default_profile = profile_name
    cfg.save()

    print(f"[green]✓ Set default profile to '{profile_name}'[/]")
