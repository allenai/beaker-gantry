import click
import rich
from beaker import Beaker, BeakerCluster, BeakerGpuType, BeakerSortOrder
from rich import print
from rich.table import Table

from .. import util
from .main import CLICK_COMMAND_DEFAULTS, main


def get_gpu_type(beaker: Beaker, cluster: BeakerCluster) -> str | None:
    nodes = list(beaker.node.list(cluster=cluster, limit=1))
    if nodes:
        try:
            return BeakerGpuType(nodes[0].node_resources.gpu_type).name.replace("_", " ")
        except ValueError:
            return None
    else:
        return None


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

    with util.init_client(ensure_workspace=False) as beaker:
        table = Table(title="Clusters", show_lines=True)
        table.add_column("Name", justify="left", no_wrap=True)
        table.add_column("Free GPUs", justify="left", no_wrap=True)
        table.add_column("GPU Type", justify="left", no_wrap=True)
        table.add_column("Slots", justify="left", no_wrap=True)

        with rich.get_console().status(
            "[i]collecting clusters...[/]", spinner="point", speed=0.8
        ) as status:
            for cluster in beaker.cluster.list(
                sort_field="free_gpus",
                sort_order=BeakerSortOrder.descending,
                include_cluster_occupancy=True,
            ):
                status.update(f"[i]collecting clusters...[/] {cluster.name}")

                if not show_all and cluster.cluster_occupancy.slot_counts.available == 0:
                    break

                gpu_type = get_gpu_type(beaker, cluster)
                if gpu_types:
                    if not gpu_type:
                        continue

                    match = gpu_type.lower()
                    for pattern in gpu_types:
                        if pattern in match:
                            gpu_type = util.highlight_pattern(gpu_type, pattern)
                            break
                    else:
                        continue

                gpus_available = cluster.cluster_occupancy.slot_counts.available
                gpus_available_style: str
                if gpus_available == 0:
                    gpus_available_style = "red"
                elif gpus_available < 8:
                    gpus_available_style = "yellow"
                else:
                    gpus_available_style = "green"

                table.add_row(
                    f"[b cyan]{cluster.name}[/]\n[u i blue]{beaker.cluster.url(cluster)}[/]",
                    f"[{gpus_available_style}]{gpus_available}[/]",
                    f"{gpu_type or 'UNKNOWN'}",
                    f"{cluster.cluster_occupancy.slot_counts.assigned}/{cluster.cluster_occupancy.slot_counts.total}",
                )

        print(table)
