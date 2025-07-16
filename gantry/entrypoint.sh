#!/usr/bin/env bash

set -eo pipefail

start_time=$(date +%s)

GANTRY_DIR="${RESULTS_DIR}/.gantry"
mkdir -p "$GANTRY_DIR"

GANTRY_LOGS_DIR="$GANTRY_DIR/logs"
mkdir -p "$GANTRY_LOGS_DIR"

RUNTIME_DIR="/gantry-runtime"
mkdir -p "$RUNTIME_DIR"
cd "$RUNTIME_DIR"

RESULTS_DATASET_URL="\e[94m\e[4mhttps://beaker.org/ds/$BEAKER_RESULT_DATASET_ID\e[0m"

CONDA_ENV_FILE="${CONDA_ENV_FILE:-environment.yml}"
PIP_REQUIREMENTS_FILE="${PIP_REQUIREMENTS_FILE:-requirements.txt}"

function log_debug {
    echo -e "\e[1m❯ [GANTRY DEBUG]\e[0m $1"
}

function log_info {
    echo -e "\e[36m\e[1m❯ [GANTRY INFO]\e[0m $1"
}

function log_warning {
    echo -e >&2 "\e[33m\e[1m❯ [GANTRY WARN]\e[0m $1"
}

function log_error {
    echo -e >&2 "\e[31m\e[1m❯ [GANTRY ERROR]\e[0m $1"
}

# usage: with_retries "max_retries" "pause_seconds" "command" "args..."
function with_retries {
    local max_retries="$1"
    shift 1
    local pause_seconds="$1"
    shift 1
    local attempts=1

    while true; do
        "$@" && return 0

        attempts=$((attempts+1)) 
        if [ $attempts -eq "$max_retries" ]; then
            log_error "Retries for exceeded for command '$*'. Check results dataset for additional logs: $RESULTS_DATASET_URL"
            exit 1
        else
            log_warning "Command '$*' failed, retrying in $pause_seconds seconds..."
            sleep "$pause_seconds"
        fi
    done
}

log_file_count=0

# usage: capture_logs "log_file" "command" "args..."
function capture_logs {
    log_file_count=$((log_file_count+1))

    local log_file
    log_file="$GANTRY_LOGS_DIR/$(printf '%03d' $log_file_count)_$1"
    shift 1

    "$@" > "$log_file" 2>&1 && return 0

    log_error "Command '$*' failed. Showing logs:"
    cat "$log_file"
    return 1
}

function path_prepend {
  for ((i=$#; i>0; i--)); do
      ARG=${!i}
      if [ -d "$ARG" ] && [[ ":$PATH:" != *":$ARG:"* ]]; then
          export PATH="$ARG${PATH:+":$PATH"}"
      fi
  done
}

function get_latest_release {
    if command -v jq &> /dev/null; then
        curl -s "https://api.github.com/repos/$1/releases/latest" | jq -r '.tag_name' | cut -d 'v' -f 2
    else
        curl -s "https://api.github.com/repos/$1/releases/latest" | grep -i "tag_name" | awk -F '"' '{print $4}' | cut -d 'v' -f 2
    fi
}

function webi_bootstrap_gh {
    curl -sS https://webi.sh/gh | sh
}

function manual_bootstrap_gh {
    local target_dir="$HOME/.local/bin"  # same place webi would install gh to
    local target_arch="386"  # or amd64

    local gh_version
    gh_version=$(get_latest_release cli/cli) || return 1
    log_debug "Resolved latest gh release to v${gh_version}"

    local target_name="gh_${gh_version}_linux_${target_arch}"
    local download_url="https://github.com/cli/cli/releases/download/v${gh_version}/${target_name}.tar.gz"

    log_debug "Downloading gh release from ${download_url}..."
    curl -sLO "$download_url" || return 1

    log_debug "Extracting release..."
    tar -xzf "${target_name}.tar.gz" || return 1

    mkdir -p "$target_dir"
    mv "$target_name/bin/gh" "$target_dir/"
    rm -rf "$target_name" "${target_name}.tar.gz"

    log_debug "Installed gh to $target_dir"
    "$target_dir/gh" --version
}

function ensure_gh {
    if ! command -v gh &> /dev/null; then
        log_info "Installing GitHub CLI..."
        # NOTE: sometimes webi has issues (https://github.com/webinstall/webi-installers/issues/1003)
        # so we fall back to a manual approach if needed.
        if ! with_retries 2 5 capture_logs "webi_bootstrap_gh.log" webi_bootstrap_gh; then
            log_warning "Falling back to manual GitHub CLI install..."
            with_retries 5 10 capture_logs "manual_bootstrap_gh.log" manual_bootstrap_gh || return 1
        fi
        path_prepend "$HOME/.local/bin"
        log_info "Done."
    fi
}

function ensure_conda {
    if ! command -v conda &> /dev/null; then
        log_info "Installing conda..."

        with_retries 5 10 curl -fsSL -o ~/miniconda.sh -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh || return 1
        chmod +x ~/miniconda.sh

        capture_logs "setup_conda.log" ~/miniconda.sh -b -p /opt/conda || return 1
        path_prepend "/opt/conda/bin"

        rm ~/miniconda.sh
        log_info "Done."
    fi

    if [[ -z "$GANTRY_CONDA_INITIALIZED" ]]; then
        log_info "Configuring conda for shell environment..."
        # Initialize conda for bash.
        # See https://stackoverflow.com/a/58081608/4151392
        eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"

        # Accept TOS for default channels.
        capture_logs "conda_tos_accept_main.log" conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || return 1
        capture_logs "conda_tos_accept_r.log" conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || return 1

        GANTRY_CONDA_INITIALIZED="1"
        log_info "Done."
    fi
}

function clone_repo {
    if [[ -z "$GIT_BRANCH" ]]; then
        if [[ -n "$GITHUB_TOKEN" ]]; then
            capture_logs "git_clone.log" gh repo clone "$GITHUB_REPO" . && return 0
        else
            capture_logs "git_clone.log" git clone "https://github.com/$GITHUB_REPO" . && return 0
        fi
    else
        log_info "Cloning from single branch '$GIT_BRANCH'..."
        if [[ -n "$GITHUB_TOKEN" ]]; then
            capture_logs "git_clone.log" gh repo clone "$GITHUB_REPO" . -- -b "$GIT_BRANCH" --single-branch && return 0
        else
            capture_logs "git_clone.log" git clone -b "$GIT_BRANCH" --single-branch "https://github.com/$GITHUB_REPO" . && return 0
        fi
    fi

    return 1
}

# get existing Python major version, e.g. '3.10'
function get_python_version {
    if command -v python &> /dev/null; then
        local python_version
        python_version=$(python --version)
        python_version=${python_version//[A-Za-z ]/}
        echo "$python_version" | cut -d"." -f1-2
    fi
}

function should_use_conda {
    if [[ -n "$NO_CONDA" ]]; then
        # Explicitly told not to use conda.
        return 1
    elif ! command -v python &> /dev/null; then
        # Need conda to install Python.
        return 0
    elif [[ -n "$VENV_NAME" ]]; then
        # Existing conda environment has been specified.
        return 0
    elif [[ -f "$CONDA_ENV_FILE" ]]; then
        # Conda environment file has been specified.
        return 0
    elif [[ -z "$PYTHON_VERSION" ]]; then
        # No Python version has been specified, so it's okay to use the default available on the image.
        return 1
    fi

    local default_python_version
    default_python_version=$(get_python_version)
    if [[ "$PYTHON_VERSION" == "$default_python_version" ]]; then
        # Default Python version on image matches specified Python version.
        return 1
    else
        # Default Python version does not match, so we need conda to get a matching version.
        return 0
    fi
}

function ensure_pip {
    log_info "Installing/upgrading PIP package manager..."

    # Use 'ensurepip' if necessary to install pip.
    if ! command -v pip &> /dev/null; then
        capture_logs "install_pip.log" python -m ensurepip
    fi

    # Upgrade pip.
    capture_logs "upgrade_pip.log" pip install --upgrade pip

    # Validate that pip is installed to the active Python environment.
    if command -v dirname &> /dev/null; then
        python_location=$(dirname "$(which python)")
        pip_location=$(dirname "$(which pip)")
        if [[ "$python_location" != "$pip_location" ]]; then
            log_warning "Install location of PIP ('$pip_location') doesn't match Python location ('$python_location')"
        fi
    fi

    log_info "Done. Using $(pip --version)"
}

echo -e "\e[36m\e[1m
##########################################
❯❯❯ [GANTRY] Validating environment... ❮❮❮
##########################################
\e[0m"

log_info "Checking for required env variables..."
for env_var in "$GITHUB_REPO" "$GIT_REF" "$RESULTS_DIR" "$BEAKER_RESULT_DATASET_ID"; do
    if [[ -z "$env_var" ]]; then
        log_error "required environment variable is empty"
        exit 1
    fi
done
log_info "Done."

log_info "Checking for required tools..."
for tool in "git" "curl"; do
    if ! command -v "$tool" &> /dev/null; then
        log_error "required tool '$tool' is not installed, please build or use an existing image that comes with '$tool'."
        exit 1
    fi
done
log_info "Done."

log_info "Results dataset $RESULTS_DATASET_URL mounted to '$RESULTS_DIR'."

if [[ -d "/var/lib/tcpxo/lib64" ]] && [[ -n "$BEAKER_REPLICA_COUNT" ]] && [[ -z "$GANTRY_SKIP_TCPXO_SETUP" ]]; then
    log_info "Configuring NCCL for GPUDirect-TCPXO..."
    log_info "Note: you can skip this step if needed by adding the flag '--skip_tcpxo_setup' to your 'gantry run ...' command."
    export NCCL_LIB_DIR="/var/lib/tcpxo/lib64"
    export LD_LIBRARY_PATH="/var/lib/tcpxo/lib64:$LD_LIBRARY_PATH"
    # shellcheck disable=SC1091
    source /var/lib/tcpxo/lib64/nccl-env-profile.sh
    export NCCL_PROTO=Simple,LL128
    export NCCL_TUNER_CONFIG_PATH=/var/lib/tcpxo/lib64/a3plus_tuner_config_ll128.textproto
    export NCCL_SHIMNET_GUEST_CONFIG_CHECKER_CONFIG_FILE=/var/lib/tcpxo/lib64/a3plus_guest_config_ll128.textproto
    log_info "Done."
fi

if [[ -n "$GITHUB_TOKEN" ]]; then
    echo -e "\e[36m\e[1m
############################################
❯❯❯ [GANTRY] Installing prerequisites... ❮❮❮
############################################
\e[0m"
    ensure_gh

    # Configure git to use the GitHub CLI as a credential helper so that we can clone private repos.
    gh auth setup-git
fi

echo -e "\e[36m\e[1m
#######################################
❯❯❯ [GANTRY] Cloning source code... ❮❮❮
#######################################
\e[0m"

git config --global advice.detachedHead false

log_info "Cloning source code..."
with_retries 5 10 clone_repo
log_info "Done."

log_info "Checking out '$GIT_REF'..."
capture_logs "git_checkout.log" git checkout "$GIT_REF"
log_info "Done."

log_info "Initializing git submodules..."
capture_logs "init_submodules.log" git submodule update --init --recursive
log_info "Done."

if [[ -z "$NO_PYTHON" ]]; then
    echo -e "\e[36m\e[1m
#######################################
❯❯❯ [GANTRY] Building Python env... ❮❮❮
#######################################
\e[0m"
    if should_use_conda; then
        ensure_conda
        
        if [[ -z "$VENV_NAME" ]]; then
            if [[ -f "$CONDA_ENV_FILE" ]]; then
                # Create from the environment file.
                log_info "Initializing environment from conda env file '$CONDA_ENV_FILE'..."
                capture_logs "conda_env_create.log" conda env create -n gantry -f "$CONDA_ENV_FILE" 
                conda activate gantry &> /dev/null
                log_info "Done."
            elif [[ -z "$PYTHON_VERSION" ]]; then
                # If the Python version hasn't been specified then we try using the default 'base' environment,
                # and otherwise create a new environment with whatever version of Python conda chooses.
                if conda activate base &> /dev/null; then
                    log_info "Using default base environment."
                else
                    log_info "Initializing environment with default Python version..."
                    capture_logs "conda_env_create.log" conda create -y -n gantry pip
                    conda activate gantry &> /dev/null
                    log_info "Done."
                fi
            else
                # Create a new empty environment with the specific Python version.
                log_info "Initializing environment with Python $PYTHON_VERSION..."
                capture_logs "conda_env_create.log" conda create -y -n gantry "python=$PYTHON_VERSION" pip
                conda activate gantry &> /dev/null
                log_info "Done."
            fi
        else
            # Check if 'VENV_NAME' is a path. If so, it should exist.
            if [[ "$VENV_NAME" == */* ]]; then
                if [[ ! -d "$VENV_NAME" ]]; then
                    log_error "conda environment '$VENV_NAME' looks like a path but it doesn't exist"
                    exit 1
                fi
            fi

            log_info "Activating specified conda environment '$VENV_NAME'..."
            conda activate "$VENV_NAME" &> /dev/null
            log_info "Done."

            if [[ -f "$CONDA_ENV_FILE" ]]; then
                log_info "Updating environment from conda env file '$CONDA_ENV_FILE'..."
                capture_logs "conda_env_update.log" conda env update -f "$CONDA_ENV_FILE"
                log_info "Done."
            fi
        fi
    elif ! command -v python &> /dev/null; then
        log_error "You specified '--no-conda', but no Python distribution can be found on the image. Please use an image with Python or remove the '--no-conda' flag."
        exit 1
    else
        log_info "Using existing $(python --version) installation at '$(which python)'."
    fi

    ensure_pip
    
    if [[ -z "$INSTALL_CMD" ]]; then
        if [[ -f 'setup.py' ]] || [[ -f 'pyproject.toml' ]] || [[ -f 'setup.cfg' ]]; then
            log_info "Installing local project..."
            if [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
                capture_logs "pip_install.log" pip install . -r "$PIP_REQUIREMENTS_FILE"
            else
                capture_logs "pip_install.log" pip install .
            fi
            log_info "Done."
        elif [[ -f "$PIP_REQUIREMENTS_FILE" ]]; then
            log_info "Installing packages from '$PIP_REQUIREMENTS_FILE'..."
            capture_logs "pip_install.log" pip install -r "$PIP_REQUIREMENTS_FILE"
            log_info "Done."
        fi
    elif [[ -f "$INSTALL_CMD" ]] && [[ "${INSTALL_CMD: -3}" == ".sh" ]]; then
        log_info "Sourcing install script '$INSTALL_CMD'..."
        # shellcheck disable=SC1090
        source "$INSTALL_CMD"
        # Reset shell behavior.
        set -eo pipefail
        set +x
        log_info "Done."
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
    
    echo "# $(python --version)" > "$GANTRY_DIR/requirements.txt"
    pip freeze >> "$GANTRY_DIR/requirements.txt"

    log_info "Using $(python --version) from '$(which python)'."
    log_info "Packages:"
    if which sed >/dev/null; then
        pip freeze | sed 's/^/- /'
    else
        pip freeze
    fi
fi

end_time=$(date +%s)
echo -e "\e[36m\e[1m
#################################
❯❯❯ [GANTRY] Setup complete ✓ ❮❮❮  (finished in $((end_time-start_time)) seconds)
#################################
\e[0m"

# Execute the arguments to this script as commands themselves.
# shellcheck disable=SC2296
exec "$@" 2>&1
