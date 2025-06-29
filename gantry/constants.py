# https://github.com/allenai/docker-images/tree/main/cuda#basic-versions
DEFAULT_IMAGE = "ai2/cuda12.8-ubuntu22.04-torch2.6.0"

ENTRYPOINT = "entrypoint.sh"

GITHUB_TOKEN_SECRET = "GITHUB_TOKEN"

CONDA_ENV_FILE = "environment.yml"

CONDA_ENV_FILE_ALTERNATE = "environment.yaml"

PIP_REQUIREMENTS_FILE = "requirements.txt"

RUNTIME_DIR = "/gantry-runtime"

RESULTS_DIR = "/results"

METRICS_FILE = f"{RESULTS_DIR}/metrics.json"
