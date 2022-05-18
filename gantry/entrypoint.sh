#!/bin/bash

set -eo pipefail

# Ensure we have all the environment variables we need.
for env_var in "$GITHUB_TOKEN" "$GITHUB_REPO" "$GIT_REF"; do
    if [[ -z "$env_var" ]]; then
        echo >&2 "error: required environment variable is empty"
        exit 1
    fi
done

# Initialize conda for bash.
# See https://stackoverflow.com/a/58081608/4151392
eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"

echo "
##############################################
# [GANTRY] [1/3] Installing prerequisites... #
##############################################
"

# Install GitHub CLI.
conda install gh --channel conda-forge

# Configure git to use GitHub CLI as a credential helper so that we can clone private repos.
gh auth setup-git

echo "
#########################################
# [GANTRY] [2/3] Cloning source code... #
#########################################
"

# Clone the repo and checkout the target commit.
gh repo clone "$GITHUB_REPO" .
git checkout "$GIT_REF"

echo "
###############################################
# [GANTRY] [3/3] Reconstructing Python env... #
###############################################
"

if [[ -z "$CONDA_ENV_FILE" ]]; then
    # shellcheck disable=SC2296
    CONDA_ENV_FILE="${{ CONDA_ENV_FILE }}"
fi
if [[ -z "$PIP_REQUIREMENTS_FILE" ]]; then
    # shellcheck disable=SC2296
    PIP_REQUIREMENTS_FILE="${{ PIP_REQUIREMENTS_FILE }}"
fi

# Reconstruct the Python environment.
venv_path="$(pwd)/.venv/"
if [[ -f "$CONDA_ENV_FILE" ]]; then
    echo "[GANTRY] Initializing environment from conda env file $CONDA_ENV_FILE..."
    conda env create -p "$venv_path" -f "$CONDA_ENV_FILE" 
elif [[ -f 'setup.py' ]] || [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
    if [[ -z "$PYTHON_VERSION" ]]; then
        echo "[GANTRY] Initializing environment with default Python version..."
        conda create -p "$venv_path" pip
    else
        echo "[GANTRY] Initializing environment with Python $PYTHON_VERSION..."
        conda create -p "$venv_path" "python=$PYTHON_VERSION" pip
    fi
else
    echo >&2 "error: at least one of 'environment.yml', 'setup.py', or 'requirements.txt' is required"
    exit 1
fi

conda activate "$venv_path"

if [[ -f 'setup.py' ]] && [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
    echo "[GANTRY] Installing package setup.py and $PIP_REQUIREMENTS_FILE..."
    pip install . -r "$PIP_REQUIREMENTS_FILE"
elif [[ -f 'setup.py' ]]; then
    echo "[GANTRY] Installing package setup.py..."
    pip install .
elif [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
    echo "[GANTRY] Installing dependencies from $PIP_REQUIREMENTS_FILE..."
    pip install -r "$PIP_REQUIREMENTS_FILE"
fi

PYTHONPATH="$(pwd)"
export PYTHONPATH

# Create directory for results.
# shellcheck disable=SC2296
mkdir -p "${{ RESULTS_DIR }}/.gantry"


echo "
#############################
# [GANTRY] Environment info #
#############################
"

echo "Using $(python --version) from $(which python)"
echo "Packages:"
if which sed >/dev/null; then
    pip freeze | sed 's/^/- /'
else
    pip freeze
fi

echo "
#############################
# [GANTRY] Setup complete ✓ #
#############################
"

# Execute the arguments to this script as commands themselves, piping output into a log file.
# shellcheck disable=SC2296
exec "$@" 2>&1 | tee "${{ RESULTS_DIR }}/.gantry/out.log"
