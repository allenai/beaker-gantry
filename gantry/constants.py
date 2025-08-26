import os

DEFAULT_IMAGE = "petew/gantry"
ENTRYPOINT = "entrypoint.sh"
GITHUB_TOKEN_SECRET = "GITHUB_TOKEN"
RUNTIME_DIR = os.environ.get("GANTRY_RUNTIME_DIR", "/gantry-runtime")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")
METRICS_FILE = f"{RESULTS_DIR}/metrics.json"
