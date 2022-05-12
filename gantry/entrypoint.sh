#!/bin/bash

set -euo pipefail

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

# Reconstruct the Python environment.
venv_path="$(pwd)/.venv/"
if [[ -f 'environment.yml' ]]; then
    conda env create -p "$venv_path" -f 'environment.yml'
elif [[ -f 'setup.py' ]] || [[ -f 'requirements.txt' ]]; then
    conda create -p "$venv_path" pip
else
    echo >&2 "error: at least one of 'environment.yml', 'setup.py', or 'requirements.txt' is required"
    exit 1
fi

conda activate "$venv_path"

if [[ -f 'setup.py' ]]; then
    pip install .
elif [[ -f 'requirements.txt' ]]; then
    pip install -r requirements.txt
fi

PYTHONPATH="$(pwd)"
export PYTHONPATH

# Create directory for results.
mkdir -p /results/.gantry


echo "
#############################
# [GANTRY] Setup complete ✓ #
#############################
"

# Execute the arguments to this script as commands themselves, piping output into a log file.
exec "$@" 2>&1 | tee /results/.gantry/out.log
