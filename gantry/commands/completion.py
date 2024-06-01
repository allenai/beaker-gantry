import os

from .main import CLICK_COMMAND_DEFAULTS, CLICK_GROUP_DEFAULTS, main


@main.group(**CLICK_GROUP_DEFAULTS)
def completion():
    """
    Generate the autocompletion script for gantry for the specified shell.

    See each sub-command's help for details on how to use the generated script.
    """


@completion.command(**CLICK_COMMAND_DEFAULTS)
def bash():
    """
    Generate the autocompletion script for bash.

    Save the output somewhere and then source the file:

    $ gantry --quiet completion bash > ~/.gantry-complete.bash && . ~/.gantry-complete.bash
    """
    os.environ["_GANTRY_COMPLETE"] = "bash_source"
    main()


@completion.command(**CLICK_COMMAND_DEFAULTS)
def fish():
    """
    Generate the autocompletion script for fish.

    Execute this once to setup completions:

    $ gantry --quiet completion fish > ~/.config/fish/completions/gantry.fish
    """
    os.environ["_GANTRY_COMPLETE"] = "fish_source"
    main()


@completion.command(**CLICK_COMMAND_DEFAULTS)
def zsh():
    """
    Generate the autocompletion script for zsh.

    Save the output somewhere and then source the file:

    $ gantry --quiet completion bash > ~/.gantry-complete.zsh && . ~/.gantry-complete.zsh
    """
    os.environ["_GANTRY_COMPLETE"] = "zsh_source"
    main()
