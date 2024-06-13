from collections import defaultdict
from typing import Dict, List

import click
from beaker import Beaker, Cluster, Node, Priority
from rich import print
from rich.progress import Progress
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

    with Progress(transient=True) as progress:
        task = progress.add_task("Collecting clusters...", start=False, total=None)
        clusters = [c for c in beaker.cluster.list() if c.is_cloud == cloud]
        progress.update(task, completed=True)

    for cluster in clusters:
        icon = "☁️" if cluster.is_cloud else "🏠"
        nodes = sorted(beaker.cluster.nodes(cluster), key=lambda node: node.hostname)
        table.add_row(
            cluster_info(cluster),
            node_info(nodes),
        )

    print(table)


def complete_cluster_name(ctx, param, incomplete) -> List[str]:
    del ctx, param
    beaker = Beaker.from_env()
    return [c.full_name for c in beaker.cluster.list() if c.full_name.startswith(incomplete)]


@cluster.command(name="util", **CLICK_COMMAND_DEFAULTS)
@click.argument(
    "cluster_name", nargs=1, required=True, type=str, shell_complete=complete_cluster_name
)
@click.option("--nodes", is_flag=True, help="Show details of each node.")
def cluster_util(cluster_name: str, nodes: bool = False):
    """
    Get the current status and utilization for a cluster.
    """
    beaker = Beaker.from_env(session=True)

    with Progress(transient=True) as progress:
        task = progress.add_task("Pulling cluster data...", start=False, total=None)
        cluster_util = beaker.cluster.utilization(cluster_name)
        cluster = cluster_util.cluster
        icon = "☁️" if cluster.is_cloud else "🏠"
        progress.update(task, completed=True)

    free_nodes = 0
    total_nodes = len(cluster_util.nodes)
    cordoned_nodes = 0
    free_gpus = 0
    total_gpus = 0
    for node_util in cluster_util.nodes:
        total_gpus += node_util.limits.gpu_count or 0
        if not node_util.cordoned:
            if node_util.running_jobs == 0:
                free_nodes += 1
            free_gpus += node_util.free.gpu_count or 0
        else:
            cordoned_nodes += 1

    running_jobs_by_priority: Dict[Priority, int] = defaultdict(int)
    running_preemptible_jobs_by_priority: Dict[Priority, int] = defaultdict(int)
    queued_jobs_by_priority: Dict[Priority, int] = defaultdict(int)
    for job in cluster_util.jobs:
        if job.priority is None:
            continue
        if job.is_running:
            running_jobs_by_priority[job.priority] += 1
            if job.is_preemptible:
                running_preemptible_jobs_by_priority[job.priority] += 1
        elif job.is_queued:
            queued_jobs_by_priority[job.priority] += 1

    def get_node_notes() -> str:
        notes = []
        if cluster.require_preemptible_tasks:
            notes.append("[yellow]All tasks must be preemptible.[/]")
        if cordoned_nodes == 1:
            notes.append(f"[yellow]{cordoned_nodes} node is cordoned.[/]")
        elif cordoned_nodes > 1:
            notes.append(f"[yellow]{cordoned_nodes} nodes are cordoned.[/]")
        return "\n".join(notes)

    summary_table = Table(
        title=f"{icon} [b magenta]{cluster.full_name}[/]\nSummary",
        show_lines=True,
        show_header=False,
    )
    summary_table.add_column("Name", justify="left", no_wrap=True)
    summary_table.add_column("Value")
    summary_table.add_row("[cyan]URL[/]", f"[i u blue]{beaker.cluster.url(cluster)}[/]")
    summary_table.add_row("[cyan]Notes[/]", get_node_notes())
    summary_table.add_row(
        "[cyan]Running jobs[/]",
        f"[bold]{cluster_util.running_jobs} total ({cluster_util.running_preemptible_jobs} preemptible)[/]\n"
        "------------------------------------------\n"
        f"[red bold i]Urgent priority:.....[/] {running_jobs_by_priority[Priority.urgent]} ({running_preemptible_jobs_by_priority[Priority.urgent]} preemptible)\n"
        f"[red i]High priority:.......[/] {running_jobs_by_priority[Priority.high]} ({running_preemptible_jobs_by_priority[Priority.high]} preemptible)\n"
        f"[green i]Normal priority:.....[/] {running_jobs_by_priority[Priority.normal]} ({running_preemptible_jobs_by_priority[Priority.normal]} preemptible)\n"
        f"[cyan i]Low priority:........[/] {running_jobs_by_priority[Priority.low]} ({running_preemptible_jobs_by_priority[Priority.low]} preemptible)\n"
        f"[blue i]Preemptible priority:[/] {running_jobs_by_priority[Priority.preemptible]}",
    )
    summary_table.add_row(
        "[cyan]Queued jobs[/]",
        f"[bold]{cluster_util.queued_jobs} total[/]\n"
        "------------------------------------------\n"
        f"[red bold i]Urgent priority:.....[/] {queued_jobs_by_priority[Priority.urgent]}\n"
        f"[red i]High priority:.......[/] {queued_jobs_by_priority[Priority.high]}\n"
        f"[green i]Normal priority:.....[/] {queued_jobs_by_priority[Priority.normal]}\n"
        f"[cyan i]Low priority:........[/] {queued_jobs_by_priority[Priority.low]}\n"
        f"[blue i]Preemptible priority:[/] {queued_jobs_by_priority[Priority.preemptible]}",
    )
    summary_table.add_row(
        "[cyan]Free nodes[/]", f"[{'green' if free_nodes else 'red'}]{free_nodes}/{total_nodes}[/]"
    )
    summary_table.add_row(
        "[cyan]Free GPUs[/]", f"[{'green' if free_gpus else 'red'}]{free_gpus}/{total_gpus}[/]"
    )

    print(summary_table)

    if nodes:
        node_table = Table(
            title=f"{icon} [b magenta]{cluster.full_name}[/]\nNodes",
            show_lines=True,
        )
        node_table.add_column("Node", justify="left", no_wrap=True)
        node_table.add_column("Jobs")
        node_table.add_column("Utilization")

        for node_util in sorted(cluster_util.nodes, key=lambda n: n.hostname):
            node_table.add_row(
                f"[i cyan]{node_util.hostname}[/]",
                f"{node_util.running_jobs} jobs ({node_util.running_preemptible_jobs} preemptible)",
                "[red]\N{ballot x} cordoned[/]"
                if node_util.cordoned
                else f"CPUs free: [{'green' if node_util.free.cpu_count else 'red'}]"
                f"{node_util.free.cpu_count} / {node_util.limits.cpu_count}[/]\n"
                f"GPUs free: [{'green' if node_util.free.gpu_count else 'red'}]"
                f"{node_util.free.gpu_count or 0} / {node_util.limits.gpu_count}[/] {node_util.free.gpu_type or ''}",
            )

        print(node_table)
