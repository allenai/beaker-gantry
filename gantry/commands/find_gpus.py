import click
import rich
from beaker import BeakerSortOrder
from rich.table import Table

from .. import beaker_utils, utils
from .main import CLICK_COMMAND_DEFAULTS, main


@main.command(name="find-gpus", **CLICK_COMMAND_DEFAULTS)
@click.option(
    "-a",
    "--all",
    "show_all",
    is_flag=True,
    help="Show all clusters, not just ones with free GPUs.",
)
@click.option(
    "-g",
    "--gpu-type",
    "gpu_types",
    type=str,
    multiple=True,
    help="""Filter by GPU type (e.g. "h100"). Multiple allowed.""",
)
def find_gpus_cmd(show_all: bool = False, gpu_types: tuple[str, ...] = tuple()):
    """
    Find free GPUs.
    """
    gpu_types = tuple(pattern.lower() for pattern in gpu_types)

    with beaker_utils.init_client(ensure_workspace=False) as beaker:
        table = Table(title="Clusters", show_lines=True)
        table.add_column("Name", justify="left", no_wrap=True)
        table.add_column("Free GPUs", justify="left", no_wrap=True)
        table.add_column("GPU Type", justify="left", no_wrap=True)
        table.add_column("Slots (used/total)", justify="left", no_wrap=True)

        with rich.get_console().status(
            "[i]collecting clusters...[/]", spinner="point", speed=0.8
        ) as status:
            for cluster in beaker.cluster.list(
                sort_field="free_gpus",
                sort_order=BeakerSortOrder.descending,
                include_cluster_occupancy=True,
            ):
                status.update(f"[i]collecting clusters...[/] {cluster.name}")

                slot_counts = cluster.cluster_occupancy.slot_counts
                if not show_all and slot_counts.available == 0:
                    break

                gpu_type = beaker_utils.get_gpu_type(beaker, cluster)
                if gpu_types:
                    if not gpu_type:
                        continue

                    match = gpu_type.lower()
                    for pattern in gpu_types:
                        if pattern in match:
                            gpu_type = utils.highlight_pattern(gpu_type, pattern)
                            break
                    else:
                        continue

                gpus_available = slot_counts.available
                gpus_available_style: str
                if gpus_available == 0:
                    gpus_available_style = "red"
                elif gpus_available < 8:
                    gpus_available_style = "yellow"
                else:
                    gpus_available_style = "green"

                table.add_row(
                    f"[b cyan]{beaker.org_name}/{cluster.name}[/]\n[blue u]{beaker.cluster.url(cluster)}[/]",
                    f"[{gpus_available_style}]{gpus_available}[/]",
                    f"{gpu_type or 'UNKNOWN'}",
                    f"{slot_counts.assigned}/{slot_counts.total - slot_counts.cordoned}"
                    + f" (cordoned: {slot_counts.cordoned})",
                )

        utils.print_stdout(table)
