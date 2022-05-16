# Saving results or metrics from an experiment

This example demonstrates how you can save results or metrics from an experiment as a Beaker dataset. In particular, the script you run just needs to write all of the files it wants to persist to the `/results` directory. The `/results/metrics.json` file is a special result file you can write to which will create **metrics** for your experiment that will be viewable from the Beaker dashboard.

To run this example:
1. Copy the contents of this directory to a new GitHub repository.
2. Commit and push all changes.
3. Run `gantry run -- python run.py`
