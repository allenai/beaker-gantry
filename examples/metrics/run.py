import gantry


def main():
    loss, accuracy = 0.13, 0.95
    gantry.api.update_workload_description(f"loss={loss:.2f}, accuracy={accuracy:.2f}")
    gantry.api.write_metrics({"loss": loss, "accuracy": accuracy})
    print("\N{check mark} Done! Metrics written to results dataset")


if __name__ == "__main__":
    main()
