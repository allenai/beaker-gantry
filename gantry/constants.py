import os

from .version import VERSION

DEFAULT_IMAGE = "beaker-py/gantry"
VERSIONED_DEFAULT_IMAGE = f"beaker-py/gantry-v{VERSION}"
ENTRYPOINT = "entrypoint.sh"
GITHUB_TOKEN_SECRET = "GITHUB_TOKEN"
RUNTIME_DIR = os.environ.get("GANTRY_RUNTIME_DIR", "/gantry-runtime")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")
METRICS_FILE = f"{RESULTS_DIR}/metrics.json"
