import os
from datetime import timedelta

import torch
import torch.distributed as dist

TRIALS = 5

# these emulate the payload which will become a M * N * 4-sized tensor below
N = 500000
M = 2000


def get_local_rank() -> int:
    return int(os.environ["LOCAL_RANK"])


def print_rank0(*args, **kwargs):
    if get_local_rank() == 0:
        print(*args, **kwargs)


def timed_allreduce(
    mat: torch.Tensor,
    start_event: torch.cuda.Event,
    end_event: torch.cuda.Event,
    device: torch.device,
):
    dist.barrier()
    start_event.record()
    dist.all_reduce(mat)
    end_event.record()

    torch.cuda.synchronize()
    duration = start_event.elapsed_time(end_event) / 1000

    size = M * N * 4  # 4 is 4 bytes in fp32
    # note that this is following the same math as NVIDIA/nccl-tests
    algbw = torch.tensor([size / duration]).to(device)

    # calculate mean across all ranks
    dist.reduce(algbw, dst=0, op=dist.ReduceOp.SUM)
    algbw /= dist.get_world_size()

    return algbw


def main():
    device = torch.device(f"cuda:{get_local_rank()}")
    torch.cuda.set_device(device)

    try:
        print_rank0("Initializing distributed process group...")
        dist.init_process_group("nccl", timeout=timedelta(seconds=30), device_id=device)
        print_rank0(f"Done. Connected to {dist.get_world_size()} processes.")

        mat = torch.rand(N, M, dtype=torch.float32).to(device)

        start_event: torch.cuda.Event = torch.cuda.Event(enable_timing=True)
        end_event: torch.cuda.Event = torch.cuda.Event(enable_timing=True)

        # do a few warm up iterations
        print_rank0("Starting warm-up...")
        for i in range(2):
            timed_allreduce(mat, start_event, end_event, device)
        print_rank0("Done.")

        # real benchmark
        print_rank0("Starting benchmark...")
        algbw_gather = []
        for i in range(TRIALS):
            print_rank0(f"Run {i+1}...")
            algbw_gather += timed_allreduce(mat, start_event, end_event, device)

        algbw = torch.mean(torch.stack(algbw_gather))

        # the 2*(n-1)/n busbw correction factor specific to all-reduce is explained here:
        # https://github.com/NVIDIA/nccl-tests/blob/master/doc/PERFORMANCE.md#allreduce
        # busbw reflects how optimally the hardware is used
        n = dist.get_world_size()
        busbw = algbw * (2 * (n - 1) / n)

        print_rank0(
            f"The average bandwidth of all_reduce with a {M*N*4/1e9}GB payload ({TRIALS} trials, {n} ranks):\n"
            f"algbw: {algbw/1e9:.3f} GBps ({algbw*8/1e9:.1f} Gbps)\n"
            f"busbw: {busbw/1e9:.3f} GBps ({busbw*8/1e9:.1f} Gbps)\n"
        )
    finally:
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
