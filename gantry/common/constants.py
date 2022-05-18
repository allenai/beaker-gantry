DEFAULT_IMAGE = "ai2/conda"

DEFAULT_CLUSTER = "ai2/general-cirrascale"

ENTRYPOINT = "entrypoint.sh"

GITHUB_TOKEN_SECRET = "GITHUB_TOKEN"

CONDA_ENV_FILE = "environment.yml"

PIP_REQUIREMENTS_FILE = "requirements.txt"

RESULTS_DIR = "/results"

METRICS_FILE = f"{RESULTS_DIR}/metrics.json"

NFS_MOUNT = "/net/nfs.cirrascale"

NFS_SUPPORTED_CLUSTERS = {
    "ai2/allennlp-cirrascale",
    "ai2/aristo-cirrascale",
    "ai2/general-cirrascale",
    "ai2/mosaic-cirrascale",
    "ai2/s2-cirrascale",
}
