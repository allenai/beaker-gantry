from typing import List

import click
from beaker import Beaker, Cluster, Node
from rich import print
from rich.table import Table

from .main import CLICK_COMMAND_DEFAULTS, CLICK_GROUP_DEFAULTS, main


@main.group(**CLICK_GROUP_DEFAULTS)
def cluster():
    """
    Get information on Beaker clusters.
    """


@cluster.command(name="list", **CLICK_COMMAND_DEFAULTS)
@click.option(
    "--cloud",
    is_flag=True,
    help="""Only show cloud clusters.""",
)
def list_clusters(cloud: bool = False):
    """
    List available clusters.

    By default only on-premise clusters are displayed.
    """
    beaker = Beaker.from_env(session=True)

    table = Table(title="Clusters", show_lines=True)
    table.add_column("Cluster", justify="left", no_wrap=True)
    table.add_column("Nodes")

    def cluster_info(cluster: Cluster) -> str:
        info = f"{icon} [b magenta]{cluster.full_name}[/], {len(nodes)} nodes"
        if (limits := cluster.node_spec) is not None:
            info += f"\nCPUs: {limits.cpu_count}\n"
            info += f"GPUs: {limits.gpu_count or 0} {'x' if limits.gpu_type else ''} {limits.gpu_type or ''}"
        return info

    def node_info(nodes: List[Node]) -> str:
        return "\n".join(
            f"[i cyan]{node.hostname}[/] - "
            f"CPUs: {node.limits.cpu_count}, "
            f"GPUs: {node.limits.gpu_count or 0} {'x' if node.limits.gpu_type else ''} {node.limits.gpu_type or ''}"
            for node in nodes
        )

    clusters = [c for c in beaker.cluster.list() if c.is_cloud == cloud]
    for cluster in clusters:
        icon = "☁️" if cluster.is_cloud else "🏠"
        nodes = sorted(beaker.cluster.nodes(cluster), key=lambda node: node.hostname)
        table.add_row(
            cluster_info(cluster),
            node_info(nodes),
        )

    print(table)


@cluster.command(name="util", **CLICK_COMMAND_DEFAULTS)
@click.argument("cluster", nargs=1, required=True, type=str)
def cluster_util(cluster: str):
    """
    Get the current status and utilization for a cluster.
    """
    beaker = Beaker.from_env(session=True)

    cluster_util = beaker.cluster.utilization(cluster)
    cluster = cluster_util.cluster
    icon = "☁️" if cluster.is_cloud else "🏠"

    table = Table(
        title=(
            f"{icon} [b magenta]{cluster.full_name}[/]\n"
            f"[i u blue]{beaker.cluster.url(cluster)}[/]\n"
            f"running jobs: {cluster_util.running_jobs} ({cluster_util.running_preemptible_jobs} preemptible)\n"
            f"queued jobs: {cluster_util.queued_jobs}"
        ),
        show_lines=True,
    )
    table.add_column("Node", justify="left", no_wrap=True)
    table.add_column("Jobs")
    table.add_column("Utilization")

    for node_util in sorted(cluster_util.nodes, key=lambda n: n.hostname):
        table.add_row(
            f"[i cyan]{node_util.hostname}[/]",
            f"{node_util.running_jobs} jobs ({node_util.running_preemptible_jobs} preemptible)",
            "[red]\N{ballot x} cordoned[/]"
            if node_util.cordoned
            else f"CPUs free: [{'green' if node_util.free.cpu_count else 'red'}]"
            f"{node_util.free.cpu_count} / {node_util.limits.cpu_count}[/]\n"
            f"GPUs free: [{'green' if node_util.free.gpu_count else 'red'}]"
            f"{node_util.free.gpu_count or 0} / {node_util.limits.gpu_count}[/] {node_util.free.gpu_type or ''}",
        )

    print(table)
