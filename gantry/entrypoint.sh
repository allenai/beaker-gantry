#!/usr/bin/env bash

set -eo pipefail

start_time=$(date +%s)

function log_info {
    echo -e "\e[36m\e[1m❯ [GANTRY]\e[0m $1"
}

function log_error {
    echo -e >&2 "\e[31m\e[1m❯ [GANTRY]\e[0m error: $1"
}

# Ensure we have all the environment variables we need.
for env_var in "$GITHUB_REPO" "$GIT_REF"; do
    if [[ -z "$env_var" ]]; then
        log_error "required environment variable is empty"
        exit 1
    fi
done

# Function to check for the GitHub CLI, install it if needed.
function ensure_gh {
    if ! command -v gh &> /dev/null; then
        log_info "Installing GitHub CLI..."
        curl -sS https://webi.sh/gh | sh > /dev/null 2>&1
        # shellcheck disable=SC1090
        source ~/.config/envman/PATH.env
        log_info "Done."
    fi
}

# Function to check for conda, install it if needed.
function ensure_conda {
    if ! command -v conda &> /dev/null; then
        log_info "Installing conda..."
        curl -fsSL -o ~/miniconda.sh -O  https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
        chmod +x ~/miniconda.sh
        ~/miniconda.sh -b -p /opt/conda
        rm ~/miniconda.sh
        export PATH="/opt/conda/bin:$PATH"
        log_info "Done."
    fi

    # Initialize conda for bash.
    # See https://stackoverflow.com/a/58081608/4151392
    eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"
}

if [[ -n "$GITHUB_TOKEN" ]]; then
    echo -e "\e[36m\e[1m
############################################
❯❯❯ [GANTRY] Installing prerequisites... ❮❮❮
############################################
\e[0m"
    # Configure git to use the GitHub CLI as a credential helper so that we can clone private repos.
    ensure_gh
    gh auth setup-git
fi

echo -e "\e[36m\e[1m
#######################################
❯❯❯ [GANTRY] Cloning source code... ❮❮❮
#######################################
\e[0m"

# shellcheck disable=SC2296
mkdir -p "${{ RUNTIME_DIR }}"
# shellcheck disable=SC2296
cd "${{ RUNTIME_DIR }}"

git config --global advice.detachedHead false

# `git clone` might occasionally fail, so we retry a couple times.
attempts=1
until [ "$attempts" -eq 5 ]
do
    if [[ -z "$GIT_BRANCH" ]]; then
        log_info "Cloning repository..."
        if [[ -n "$GITHUB_TOKEN" ]]; then
            gh repo clone "$GITHUB_REPO" . && break
        else
            git clone "https://github.com/$GITHUB_REPO" . && break
        fi
    else
        log_info "Cloning single branch '$GIT_BRANCH' of repository..."
        if [[ -n "$GITHUB_TOKEN" ]]; then
            gh repo clone "$GITHUB_REPO" . -- -b "$GIT_BRANCH" --single-branch && break
        else
            git clone -b "$GIT_BRANCH" --single-branch "https://github.com/$GITHUB_REPO" . && break
        fi
    fi
    attempts=$((attempts+1)) 
    sleep 10
done

if [ $attempts -eq 5 ]; then
    log_error "failed to clone $GITHUB_REPO after $attempts tries"
    exit 1
fi

git checkout "$GIT_REF"
git submodule update --init --recursive
log_info "Done."

if [[ -z "$NO_PYTHON" ]]; then
    echo -e "\e[36m\e[1m
#######################################
❯❯❯ [GANTRY] Building Python env... ❮❮❮
#######################################
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
                log_error "venv '$VENV_NAME' looks like a path but it doesn't exist"
                exit 1
            fi
        fi
        
        if conda activate "$VENV_NAME" &> /dev/null; then
            log_info "Using existing conda environment '$VENV_NAME'"
            # The virtual environment already exists. Possibly update it based on an environment file.
            if [[ -f "$CONDA_ENV_FILE" ]]; then
                log_info "Updating environment from conda env file '$CONDA_ENV_FILE'..."
                conda env update -f "$CONDA_ENV_FILE"
                log_info "Done."
            fi
        else
            # The virtual environment doesn't exist yet. Create it.
            if [[ -f "$CONDA_ENV_FILE" ]]; then
                # Create from the environment file.
                log_info "Initializing environment from conda env file '$CONDA_ENV_FILE'..."
                conda env create -n "$VENV_NAME" -f "$CONDA_ENV_FILE" 
                log_info "Done."
            elif [[ -z "$PYTHON_VERSION" ]]; then
                # Create a new empty environment with the whatever the default Python version is.
                log_info "Initializing environment with default Python version..."
                conda create -y -n "$VENV_NAME" pip
                log_info "Done."
            else
                # Create a new empty environment with the specific Python version.
                log_info "Initializing environment with Python $PYTHON_VERSION..."
                conda create -y -n "$VENV_NAME" "python=$PYTHON_VERSION" pip
                log_info "Done."
            fi
            conda activate "$VENV_NAME"
        fi
    fi
    
    if [[ -z "$INSTALL_CMD" ]]; then
        # Check for a 'requirements.txt' and/or 'setup.py/pyproject.toml/setup.cfg' file.
        if { [[ -f 'setup.py' ]] || [[ -f 'pyproject.toml' ]] || [[ -f 'setup.cfg' ]]; } && [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
            log_info "Installing local project and packages from '$PIP_REQUIREMENTS_FILE'..."
            pip install . -r "$PIP_REQUIREMENTS_FILE"
            log_info "Done."
        elif [[ -f 'setup.py' ]] || [[ -f 'pyproject.toml' ]] || [[ -f 'setup.cfg' ]]; then
            log_info "Installing local project..."
            pip install .
            log_info "Done."
        elif [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
            log_info "Installing packages from '$PIP_REQUIREMENTS_FILE'..."
            pip install -r "$PIP_REQUIREMENTS_FILE"
            log_info "Done."
        fi
    else
        log_info "Installing packages with given command: $INSTALL_CMD"
        eval "$INSTALL_CMD"
        log_info "Done."
    fi
    
    if [[ -z "$PYTHONPATH" ]]; then
        PYTHONPATH="$(pwd)"
    else
        PYTHONPATH="${PYTHONPATH}:$(pwd)"
    fi
    export PYTHONPATH
    
    
    echo -e "\e[36m\e[1m
########################################
❯❯❯ [GANTRY] Python environment info ❮❮❮
########################################
\e[0m"
    
    log_info "Using $(python --version) from $(which python)"
    log_info "Packages:"
    if which sed >/dev/null; then
        pip freeze | sed 's/^/- /'
    else
        pip freeze
    fi
fi

echo -e "\e[36m\e[1m
##########################################
❯❯❯ [GANTRY] Finalizing environment... ❮❮❮
##########################################
\e[0m"
# Create directory for results.
log_info "Creating results dir at '${RESULTS_DIR}'..."
mkdir -p "${RESULTS_DIR}/.gantry"
log_info "Done."

echo -e "\e[36m\e[1m
#################################
❯❯❯ [GANTRY] Setup complete ✓ ❮❮❮
#################################
\e[0m"

end_time=$(date +%s)
log_info "Finished setup in $((end_time-start_time)) seconds"

# Execute the arguments to this script as commands themselves.
# shellcheck disable=SC2296
exec "$@" 2>&1
