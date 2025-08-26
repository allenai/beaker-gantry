from gantry.api import write_metrics


def main():
    write_metrics({"loss": 0.1, "accuracy": 0.95})
    print("\N{check mark} Done! Metrics written to results dataset")


if __name__ == "__main__":
    main()
