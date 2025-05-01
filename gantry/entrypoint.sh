#!/usr/bin/env bash

set -eo pipefail

# Ensure we have all the environment variables we need.
for env_var in "$GITHUB_REPO" "$GIT_REF"; do
    if [[ -z "$env_var" ]]; then
        echo -e >&2 "\e[31m\e[1m❯ [GANTRY]\e[0m error: required environment variable is empty"
        exit 1
    fi
done

# Function to check for conda, install it if needed.
function ensure_conda {
    if ! command -v conda &> /dev/null; then
        echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Installing conda..."
        curl -fsSL -o ~/miniconda.sh -O  https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
        chmod +x ~/miniconda.sh
        ~/miniconda.sh -b -p /opt/conda
        rm ~/miniconda.sh
        export PATH="/opt/conda/bin:$PATH"
    fi

    # Initialize conda for bash.
    # See https://stackoverflow.com/a/58081608/4151392
    eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"
}

if [[ -n "$GITHUB_TOKEN" ]]; then
    echo -e "\e[36m\e[1m
########################################
❯ [GANTRY] Installing prerequisites... #
########################################
\e[0m"
    if ! command -v gh &> /dev/null; then
        if [[ -z "$NO_CONDA" ]]; then
            ensure_conda
        else
            echo -e >&2 "\e[31m\e[1m❯ [GANTRY]\e[0m error: you specified '--no-conda' but conda is needed to install the GitHub CLI. To avoid this error please ensure the GitHub CLI is already installed on your image."
        fi

        # Install GitHub CLI.
        conda install -y gh --channel conda-forge
    fi
    
    # Configure git to use GitHub CLI as a credential helper so that we can clone private repos.
    gh auth setup-git
fi

echo -e "\e[36m\e[1m
###################################
❯ [GANTRY] Cloning source code... #
###################################
\e[0m"

# shellcheck disable=SC2296
mkdir -p "${{ RUNTIME_DIR }}"
# shellcheck disable=SC2296
cd "${{ RUNTIME_DIR }}"

# `git clone` might occasionally fail, so we retry a couple times.
attempts=1
until [ "$attempts" -eq 5 ]
do
    if [[ -n "$GITHUB_TOKEN" ]]; then
        gh repo clone "$GITHUB_REPO" . && break
    else
        git clone "https://github.com/$GITHUB_REPO" . && break
    fi
    attempts=$((attempts+1)) 
    sleep 10
done

if [ $attempts -eq 5 ]; then
  echo -e >&2 "\e[31m\e[1m❯ [GANTRY]\e[0m error: failed to clone $GITHUB_REPO after $attempts tries"
  exit 1
fi

git checkout "$GIT_REF"
git submodule update --init --recursive

if [[ -z "$NO_PYTHON" ]]; then
    echo -e "\e[36m\e[1m
###################################
❯ [GANTRY] Building Python env... #
###################################
\e[0m"
    
    if [[ -z "$VENV_NAME" ]]; then
        VENV_NAME=venv
    fi
    if [[ -z "$CONDA_ENV_FILE" ]]; then
        # shellcheck disable=SC2296
        CONDA_ENV_FILE="${{ CONDA_ENV_FILE }}"
    fi
    if [[ -z "$PIP_REQUIREMENTS_FILE" ]]; then
        # shellcheck disable=SC2296
        PIP_REQUIREMENTS_FILE="${{ PIP_REQUIREMENTS_FILE }}"
    fi
    
    if [[ -z "$NO_CONDA" ]]; then
        ensure_conda

        # Check if VENV_NAME is a path. If so, it should exist.
        if [[ "$VENV_NAME" == */* ]]; then
            if [[ ! -d "$VENV_NAME" ]]; then
                echo -e >&2 "\e[31m\e[1m❯ [GANTRY]\e[0m error: venv '$VENV_NAME' looks like a path but it doesn't exist"
                exit 1
            fi
        fi
        
        if conda activate "$VENV_NAME" &> /dev/null; then
            echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Using existing conda environment '$VENV_NAME'"
            # The virtual environment already exists. Possibly update it based on an environment file.
            if [[ -f "$CONDA_ENV_FILE" ]]; then
                echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Updating environment from conda env file '$CONDA_ENV_FILE'..."
                conda env update -f "$CONDA_ENV_FILE"
            fi
        else
            # The virtual environment doesn't exist yet. Create it.
            if [[ -f "$CONDA_ENV_FILE" ]]; then
                # Create from the environment file.
                echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Initializing environment from conda env file '$CONDA_ENV_FILE'..."
                conda env create -n "$VENV_NAME" -f "$CONDA_ENV_FILE" 
            elif [[ -z "$PYTHON_VERSION" ]]; then
                # Create a new empty environment with the whatever the default Python version is.
                echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Initializing environment with default Python version..."
                conda create -y -n "$VENV_NAME" pip
            else
                # Create a new empty environment with the specific Python version.
                echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Initializing environment with Python $PYTHON_VERSION..."
                conda create -y -n "$VENV_NAME" "python=$PYTHON_VERSION" pip
            fi
            conda activate "$VENV_NAME"
        fi
    fi
    
    if [[ -z "$INSTALL_CMD" ]]; then
        # Check for a 'requirements.txt' and/or 'setup.py/pyproject.toml/setup.cfg' file.
        if { [[ -f 'setup.py' ]] || [[ -f 'pyproject.toml' ]] || [[ -f 'setup.cfg' ]]; } && [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
            echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Installing local project and packages from '$PIP_REQUIREMENTS_FILE'..."
            pip install . -r "$PIP_REQUIREMENTS_FILE"
        elif [[ -f 'setup.py' ]] || [[ -f 'pyproject.toml' ]] || [[ -f 'setup.cfg' ]]; then
            echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Installing local project..."
            pip install .
        elif [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
            echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Installing packages from '$PIP_REQUIREMENTS_FILE'..."
            pip install -r "$PIP_REQUIREMENTS_FILE"
        fi
    else
        echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Installing packages with given command: $INSTALL_CMD"
        eval "$INSTALL_CMD"
    fi
    
    if [[ -z "$PYTHONPATH" ]]; then
        PYTHONPATH="$(pwd)"
    else
        PYTHONPATH="${PYTHONPATH}:$(pwd)"
    fi
    export PYTHONPATH
    
    
    echo -e "\e[36m\e[1m
####################################
❯ [GANTRY] Python environment info #
####################################
\e[0m"
    
    echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Using $(python --version) from $(which python)"
    echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Packages:"
    if which sed >/dev/null; then
        pip freeze | sed 's/^/- /'
    else
        pip freeze
    fi
fi

echo -e "\e[36m\e[1m
######################################
❯ [GANTRY] Finalizing environment... #
######################################
\e[0m"
# Create directory for results.
echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m Creating results dir at '${RESULTS_DIR}'..."
mkdir -p "${RESULTS_DIR}/.gantry"

echo -e "\e[36m\e[1m
#############################
❯ [GANTRY] Setup complete ✓ #
#############################
\e[0m"

# Execute the arguments to this script as commands themselves.
# shellcheck disable=SC2296
exec "$@" 2>&1
