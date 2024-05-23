import click
from beaker import Beaker

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
    clusters = [c for c in beaker.cluster.list() if c.is_cloud == cloud]
    for cluster in clusters:
        icon = "☁️" if cluster.is_cloud else "🏠"
        print(f"{icon} [b magenta]{cluster.full_name}[/]")
        for node in sorted(beaker.cluster.nodes(cluster), key=lambda node: node.hostname):
            print(
                f"   [i cyan]{node.hostname}[/] - "
                f"CPUs: {node.limits.cpu_count}, "
                f"GPUs: {node.limits.gpu_count or 0} {'x' if node.limits.gpu_type else ''} {node.limits.gpu_type or ''}"
            )
        if cluster.node_spec is not None:
            limits = cluster.node_spec
            print(
                f"  CPUs: {limits.cpu_count}, "
                f"GPUs: {limits.gpu_count or 0} {'x' if limits.gpu_type else ''} {limits.gpu_type or ''}"
            )


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
    print(
        f"{icon} [b magenta]{cluster.full_name}[/]\n\n"
        f"running jobs: {cluster_util.running_jobs} ({cluster_util.running_preemptible_jobs} preemptible)\n"
        f"queued jobs: {cluster_util.queued_jobs}"
    )
    if cluster_util.nodes:
        print("nodes:")
    for node in sorted(cluster_util.nodes, key=lambda n: n.hostname):
        print(
            f"  [i cyan]{node.hostname}[/] - {node.running_jobs} jobs ({node.running_preemptible_jobs} preemptible)\n"
            f"    CPUs free: [{'green' if node.free.cpu_count else 'red'}]"
            f"{node.free.cpu_count} / {node.limits.cpu_count}[/]\n"
            f"    GPUs free: [{'green' if node.free.gpu_count else 'red'}]"
            f"{node.free.gpu_count or 0} / {node.limits.gpu_count}[/] {node.free.gpu_type or ''}\n"
        )


@cluster.command(name="allow-preemptible", **CLICK_COMMAND_DEFAULTS)
@click.argument("cluster", nargs=1, required=True, type=str)
def cluster_allow_preemptible(cluster: str):
    """
    Allow preemptible jobs on the cluster.
    """
    beaker = Beaker.from_env(session=True)
    beaker.cluster.update(cluster, allow_preemptible=True)
    print("[green]\N{check mark} Preemptible jobs allowed[/]")


@cluster.command(name="disallow-preemptible", **CLICK_COMMAND_DEFAULTS)
@click.argument("cluster", nargs=1, required=True, type=str)
def cluster_disallow_preemptible(cluster: str):
    """
    Disallow preemptible jobs on the cluster.
    """
    beaker = Beaker.from_env(session=True)
    beaker.cluster.update(cluster, allow_preemptible=False)
    print("[yellow]\N{ballot x} Preemptible jobs disallowed[/]")
