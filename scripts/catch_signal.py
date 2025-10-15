import os
import signal


def _handle_os_signal(signalnum, stack_frame):
    del stack_frame

    signame: str | None = None
    if signalnum == signal.SIGTERM:
        signame = "SIGTERM"
    elif signalnum == signal.SIGINT:
        signame = "SIGINT"

    msg: str
    if signame is not None:
        msg = f"{signame} received"
    else:
        msg = f"Sig({signalnum}) received"

    print(msg)


if __name__ == "__main__":
    if os.environ.get("BEAKER_REPLICA_RANK") == "0":
        signal.signal(signal.SIGTERM, _handle_os_signal)
        signal.signal(signal.SIGINT, _handle_os_signal)
        print("Waiting for signals (SIGTERM, SIGINT)...")
        signal.pause()
        print("Exiting...")
    else:
        raise RuntimeError("Not the main replica, failing now...")
