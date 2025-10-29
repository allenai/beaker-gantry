"""
Gantry's public API.
"""

import os
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Literal

from beaker import Beaker

from . import beaker_utils
from .callbacks import *
from .git_utils import GitRepoState
from .launch import follow_workload, launch_experiment
from .recipe import Recipe

__all__ = [
    "Recipe",
    "GitRepoState",
    "Callback",
    "SlackCallback",
    "launch_experiment",
    "follow_workload",
    "update_workload_description",
    "write_metrics",
]


_ORIGINAL_WORKLOAD_DESCRIPTIONS: dict[str, str] = {}


def update_workload_description(
    description: str,
    strategy: Literal["append", "prepend", "replace"] = "replace",
    beaker_token: str | None = None,
    client: Beaker | None = None,
) -> str:
    """
    Update the description of the Gantry workload that this process is running in.

    :param description: The description to set or add, depending on the ``strategy``.
    :param strategy: One of "append", "prepend", or "replace" to indicate how the new description
        should be combined with the original description. Defaults to "replace".
    :param beaker_token: An optional Beaker API token to use. If not provided, the
        ``BEAKER_TOKEN`` environment variable will be used if set, or a Beaker config file.
        Alternatively you can provide an existing :class:`~beaker.Beaker` client via the
        ``client`` parameter.
    :param client: An optional existing :class:`~beaker.Beaker` client to use. If not provided,
        a new client will be created using the provided ``beaker_token`` or environment/config.
    """
    global _ORIGINAL_WORKLOAD_DESCRIPTIONS

    if (workload_id := os.environ.get("BEAKER_WORKLOAD_ID")) is None:
        raise RuntimeError(
            "'update_workload_description' can only be called from within a running workload"
        )

    with ExitStack() as stack:
        if client is None:
            beaker: Beaker = stack.enter_context(
                beaker_utils.init_client(
                    ensure_workspace=False, beaker_token=beaker_token, check_for_upgrades=False
                )
            )
        else:
            beaker = client

        workload = beaker.workload.get(workload_id)
        if workload_id not in _ORIGINAL_WORKLOAD_DESCRIPTIONS:
            _ORIGINAL_WORKLOAD_DESCRIPTIONS[workload_id] = (
                workload.experiment.description or ""
            ).strip()

        og_description = _ORIGINAL_WORKLOAD_DESCRIPTIONS[workload_id]

        if strategy == "append":
            description = og_description + " " + description
        elif strategy == "prepend":
            description = description + " " + og_description
        elif strategy != "replace":
            raise ValueError(
                f"'strategy' must be one of 'append', 'prepend', or 'replace', but got '{strategy}'."
            )

        description = description.strip()
        beaker.workload.update(workload, description=description)

    return description


def write_metrics(metrics: dict[str, Any]):
    """
    Write result metrics for the Gantry workload that this process is running in.

    :param metrics: A JSON-serializable dictionary of metrics to write.
    """
    import json

    if os.environ.get("BEAKER_WORKLOAD_ID") is None:
        raise RuntimeError("'write_metrics' can only be called from within a running workload")
    if (results_dir := os.environ.get("RESULTS_DIR")) is None:
        raise RuntimeError("Results directory not set! Can't write metrics.")
    metrics_path = Path(results_dir) / "metrics.json"
    metrics_path.parent.mkdir(exist_ok=True, parents=True)
    with metrics_path.open("w") as f:
        json.dump(metrics, f)
