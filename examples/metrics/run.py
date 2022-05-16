import json

from gantry import METRICS_FILE


def main():
    with open(METRICS_FILE, "w") as f:
        json.dump({"loss": 0.1, "accuracy": 0.95}, f)
    print(f"\N{check mark} Done! Metrics written to {METRICS_FILE}")


if __name__ == "__main__":
    main()
