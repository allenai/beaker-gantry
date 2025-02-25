import argparse

import requests

from gantry.version import VERSION


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        "slack-notifier", description="Send a release notifcation to a Slack channel."
    )
    parser.add_argument("webhook_url", type=str, help="The webhook URL for a Slack channel.")
    return parser.parse_args()


def main():
    args = parse_args()
    text = (
        f"beaker-gantry *v{VERSION}* is now out. See "
        f"https://github.com/allenai/beaker-gantry/releases/tag/v{VERSION} for release notes."
    )
    requests.post(args.webhook_url, json={"text": text})


if __name__ == "__main__":
    main()
