#!/usr/bin/env bash

function set_shell_defaults {
    set +x -eo pipefail
}

set_shell_defaults

start_time=$(date +%s)

RESULTS_DIR="${RESULTS_DIR:-/results}"
mkdir -p "$RESULTS_DIR"

GANTRY_DIR="${RESULTS_DIR}/.gantry"
mkdir -p "$GANTRY_DIR"

GANTRY_LOGS_DIR="$GANTRY_DIR/logs"
mkdir -p "$GANTRY_LOGS_DIR"

GANTRY_RUNTIME_DIR="${GANTRY_RUNTIME_DIR:-/gantry-runtime}"
mkdir -p "$GANTRY_RUNTIME_DIR"
cd "$GANTRY_RUNTIME_DIR"

RESULTS_DATASET_URL="\e[94m\e[4mhttps://beaker.org/ds/$BEAKER_RESULT_DATASET_ID\e[0m"

GANTRY_PYTHON_MANAGER="${GANTRY_PYTHON_MANAGER:-uv}"

###################################################################################################
#################################### Start helper functions... ####################################
###################################################################################################

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

function log_header {
    local header="### [GANTRY] $1 ###"
    local header_border="${header//?/#}"
    echo -e "\e[36m\e[1m
$header_border
$header  $2
$header_border
\e[0m"
}

function has_infiniband {
    # See https://beaker-docs.apps.allenai.org/experiments/distributed-training.html
    # for list of clusters with InfiniBand.
    if [[ $BEAKER_NODE_HOSTNAME == "jupiter"* ]]; then
        return 0
    elif [[ $BEAKER_NODE_HOSTNAME == "titan"* ]]; then
        return 0
    elif [[ $BEAKER_NODE_HOSTNAME == "ceres"* ]]; then
        return 0
    else
        return 1
    fi
}

function log_physical_host_topology {
    if [[ $BEAKER_NODE_HOSTNAME == "augusta"* ]]; then
        local instance_id
        local topology
        local metadata
        instance_id=$(curl -s -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/id) || return 1
        topology=$(curl -s -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/attributes/physical_host_topology | tr -d '[:space:]') || return 1
        metadata=$(printf 'GoogleInstanceMetadata: {"id":"%s","physical_host_topology":%s}\n' "$instance_id" "$topology")
        log_info "$metadata"
    fi
    return 0
}

function is_multi_node_gpu_job {
    if [[ -n "$BEAKER_REPLICA_COUNT" ]] &&
       ((BEAKER_REPLICA_COUNT > 1)) &&
       [[ -n "$BEAKER_LEADER_REPLICA_HOSTNAME" ]] &&
       [[ -n "$BEAKER_ASSIGNED_GPU_COUNT" ]] &&
       ((BEAKER_ASSIGNED_GPU_COUNT > 0)); then
        return 0
    else
        return 1
    fi
}

# usage: with_retries MAX_RETRIES(INT) COMMAND(TEXT) [ARGS(ANY)...]
function with_retries {
    local max_retries="$1"
    shift 1
    local attempts=0

    while true; do
        "$@" && return 0

        if ((++attempts >= max_retries)); then
            log_error "Retries exceeded. Check results dataset for additional logs: $RESULTS_DATASET_URL"
            return 1
        else
            local pause_seconds=$((2**(attempts-1)))
            if ((pause_seconds > 30)); then
                pause_seconds=30
            fi
            log_warning "Attempt ${attempts}/${max_retries} failed. Retrying in ${pause_seconds} second(s)..."
            sleep "$pause_seconds"
        fi
    done
}

log_file_count=0

# usage: capture_logs NAME(TEXT) COMMAND(TEXT) [ARGS(ANY)...]
function capture_logs {
    log_file_count=$((log_file_count+1))

    local log_file
    log_file="$GANTRY_LOGS_DIR/$(printf '%03d' $log_file_count)_$1.log"
    shift 1

    "$@" > "$log_file" 2>&1 && return 0

    log_error "Command '$*' failed. Showing logs:"
    cat "$log_file"
    return 1
}

function path_prepend {
  for ((i=$#; i>0; i--)); do
      ARG=${!i}
      if [[ -d "$ARG" ]] && [[ ":$PATH:" != *":$ARG:"* ]]; then
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

function webi_bootstrap_jq {
    curl -sS https://webi.sh/jq | sh
}

function ensure_jq {
    if ! command -v jq &> /dev/null; then
        log_info "Installing jq..."
        with_retries 5 capture_logs "webi_bootstrap_jq" webi_bootstrap_jq || return 1
        path_prepend ~/.local/bin
        log_info "Done. Installed $(jq --version)."
    fi
}

function webi_bootstrap_gh {
    curl -sS https://webi.sh/gh | sh
}

function manual_bootstrap_gh {
    local target_dir=~/.local/bin  # same place webi would install gh to
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
    mv "$target_name/bin/gh" "$target_dir/" || return 1
    rm -rf "$target_name" "${target_name}.tar.gz"

    log_debug "Installed gh to $target_dir"
    "$target_dir/gh" --version
}

function ensure_gh {
    if ! command -v gh &> /dev/null; then
        log_info "Installing GitHub CLI..."
        # NOTE: sometimes webi has issues (https://github.com/webinstall/webi-installers/issues/1003)
        # so we fall back to a manual approach if needed.
        if ! with_retries 2 capture_logs "webi_bootstrap_gh" webi_bootstrap_gh; then
            log_warning "Falling back to manual GitHub CLI install..."
            with_retries 5 capture_logs "manual_bootstrap_gh" manual_bootstrap_gh || return 1
        fi
        path_prepend ~/.local/bin
        log_info "Done. Installed $(gh --version | head -n 1)."
    else
        log_info "Using $(gh --version | head -n 1)."
    fi
}

function ensure_conda {
    if ! command -v conda &> /dev/null; then
        log_info "Installing conda..."

        with_retries 5 capture_logs "download_miniconda" curl -fsSL -o ~/miniconda.sh -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh || return 1
        chmod +x ~/miniconda.sh

        capture_logs "setup_conda" ~/miniconda.sh -b -p /opt/conda || return 1
        path_prepend "/opt/conda/bin"

        rm ~/miniconda.sh
        log_info "Done. Installed $(conda --version)."
    fi

    if [[ -z "$GANTRY_CONDA_INITIALIZED" ]]; then
        log_info "Configuring $(conda --version) for shell environment..."
        # Initialize conda for bash.
        # See https://stackoverflow.com/a/58081608/4151392
        eval "$(command conda 'shell.bash' 'hook' 2> /dev/null)"

        # Accept TOS for default channels.
        # NOTE: this will fail if the conda version is too old.
        if command conda tos &> /dev/null 2>&1; then
            capture_logs "conda_tos_accept_main" conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
            capture_logs "conda_tos_accept_r" conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
        fi

        GANTRY_CONDA_INITIALIZED="1"
        log_info "Done."
    fi
}

function bootstrap_uv {
    curl -LsSf https://astral.sh/uv/install.sh | sh
}

function ensure_uv {
    if ! command -v uv &> /dev/null; then
        log_info "Installing uv..."
        with_retries 5 capture_logs "bootstrap_uv" bootstrap_uv || return 1
        path_prepend ~/.cargo/bin ~/.local/bin
        log_info "Done. Installed $(uv --version)."
    else
        log_info "Using $(uv --version)."
    fi
}

function ensure_pip {
    log_info "Installing/upgrading PIP package manager..."

    # Use 'ensurepip' if necessary to install pip.
    if ! command -v pip &> /dev/null; then
        capture_logs "install_pip" python -m ensurepip
    fi

    # Upgrade pip.
    capture_logs "upgrade_pip" pip install --upgrade pip

    # Validate that pip is installed to the active Python environment.
    if command -v dirname &> /dev/null; then
        python_location=$(dirname "$(which python)")
        pip_location=$(dirname "$(which pip)")
        if [[ "$python_location" != "$pip_location" ]]; then
            log_warning "Install location of PIP ('$pip_location') doesn't match Python location ('$python_location')"
        fi
    fi

    log_info "Done. Using $(pip --version)."
}

function run_custom_cmd {
    local custom_cmd_purpose=$1
    local custom_cmd=$2
    if [[ -f "$custom_cmd" ]] && [[ "${custom_cmd: -3}" == ".sh" ]]; then
        log_info "Sourcing user-defined ${custom_cmd_purpose} script '${custom_cmd}'..."

        # shellcheck disable=SC1090
        source "$custom_cmd" || return 1

        # Reset shell behavior.
        set_shell_defaults

        log_info "Done."
    else
        log_info "Running user-defined ${custom_cmd_purpose} command: '${custom_cmd}'"
        eval "$custom_cmd" || return 1
        log_info "Done."
    fi
}

function uv_install_project {
    local project_file=$1
    shift 1

    log_info "Installing local project..."
    capture_logs "uv_pip_install" uv pip install "$@" -r "$project_file" . || return 1
    log_info "Done."
}

function uv_install_requirements {
    log_info "Installing packages from requirements.txt..."
    capture_logs "uv_pip_install" uv pip install "$@" -r requirements.txt || return 1
    log_info "Done."
}

function uv_setup_python {
    ensure_uv || return 1

    GANTRY_UV_FLAGS=""

    if [[ -n "$GANTRY_UV_ALL_EXTRAS" ]]; then
        GANTRY_UV_FLAGS="$GANTRY_UV_FLAGS --all-extras"
    elif [[ -n "$GANTRY_UV_EXTRAS" ]]; then
        for extra_name in $GANTRY_UV_EXTRAS; do
            GANTRY_UV_FLAGS="$GANTRY_UV_FLAGS --extra=$extra_name"
        done
    fi

    if [[ -n "$GANTRY_UV_VENV" ]]; then
        if [[ ! -d "$GANTRY_UV_VENV" ]] || [[ ! -f "$GANTRY_UV_VENV/bin/activate" ]]; then
            log_error "'GANTRY_UV_VENV' (--uv-venv) '$GANTRY_UV_VENV' should be a path to a virtual env directory"
            return 1
        fi

        log_info "Activating virtual environment at '$GANTRY_UV_VENV'..."
        # shellcheck disable=SC1091
        source "$GANTRY_UV_VENV/bin/activate" || return 1
        log_info "Done."
    elif [[ -n "$GANTRY_USE_SYSTEM_PYTHON" ]]; then
        if ! command -v python &> /dev/null; then
            log_error "No system python found. If your image doesn't include a Python distribution you should omit the 'GANTRY_USE_SYSTEM_PYTHON' (--system-python) flag."
            return 1
        fi

        log_info "Using existing $(python --version) installation at '$(which python)'."
        GANTRY_UV_FLAGS="$GANTRY_UV_FLAGS --system --break-system-packages"
    elif [[ -n "$GANTRY_DEFAULT_PYTHON_VERSION" ]]; then
        log_info "Creating virtual environment with Python ${GANTRY_DEFAULT_PYTHON_VERSION}..."
        capture_logs "uv_venv_create" uv venv --python="$GANTRY_DEFAULT_PYTHON_VERSION" || return 1
        log_info "Done."

        log_info "Activating virtual environment..."
        # shellcheck disable=SC1091
        source .venv/bin/activate || return 1
        log_info "Done."
    else 
        log_info "Creating virtual environment..."
        capture_logs "uv_venv_create" uv venv || return 1
        log_info "Done."

        log_info "Activating virtual environment..."
        # shellcheck disable=SC1091
        source .venv/bin/activate || return 1
        log_info "Done."
    fi

    UV_PYTHON="$(which python)"
    export UV_PYTHON

    if [[ -z "$GANTRY_INSTALL_CMD" ]]; then
        if [[ -f 'pyproject.toml' ]]; then
            # shellcheck disable=SC2086
            uv_install_project pyproject.toml $GANTRY_UV_FLAGS || return 1
        elif [[ -f 'setup.py' ]]; then
            # shellcheck disable=SC2086
            uv_install_project setup.py $GANTRY_UV_FLAGS || return 1
        elif [[ -f 'setup.cfg' ]]; then
            # shellcheck disable=SC2086
            uv_install_project setup.cfg $GANTRY_UV_FLAGS || return 1
        elif [[ -f 'requirements.txt' ]]; then
            # shellcheck disable=SC2086
            uv_install_requirements $GANTRY_UV_FLAGS || return 1
        fi
    else
        run_custom_cmd "install" "$GANTRY_INSTALL_CMD" || return 1
    fi

    uv pip freeze 2> /dev/null > "$GANTRY_DIR/requirements.txt"
}

function conda_setup_python {
    # Validate some options.
    # --conda-file should be a file if given.
    if [[ -n "$GANTRY_CONDA_FILE" ]] && [[ ! -f "$GANTRY_CONDA_FILE" ]]; then
        log_error "conda environment file '$GANTRY_CONDA_FILE' not found."
        return 1
    fi
    # If --conda-env looks like a path, it should point to a directory.
    if [[ -n "$GANTRY_CONDA_ENV" ]] && [[ "$GANTRY_CONDA_ENV" == */* ]]; then
        if [[ ! -d "$GANTRY_CONDA_ENV" ]]; then
            log_error "conda environment '$GANTRY_CONDA_ENV' looks like a path but it doesn't exist"
            return 1
        fi
    fi

    ensure_conda || return 1

    if [[ -n "$GANTRY_CONDA_ENV" ]]; then
        log_info "Activating conda environment '$GANTRY_CONDA_ENV'..."
        conda activate "$GANTRY_CONDA_ENV" &> /dev/null || return 1
        log_info "Done."

        if [[ -f "$GANTRY_CONDA_FILE" ]]; then
            log_info "Updating environment from conda env file '$GANTRY_CONDA_FILE'..."
            capture_logs "conda_env_update" conda env update -f "$GANTRY_CONDA_FILE" || return 1
            log_info "Done."
        fi
    elif [[ -n "$GANTRY_USE_SYSTEM_PYTHON" ]]; then
        # Try using the default 'base' environment.
        if conda activate base &> /dev/null; then
            log_info "Using default conda base environment."
        else
            log_error "No conda base environment found, which is required due to the 'GANTRY_USE_SYSTEM_PYTHON' (--system-python) flag"
            return 1
        fi

        if [[ -f "$GANTRY_CONDA_FILE" ]]; then
            log_info "Updating environment from conda env file '$GANTRY_CONDA_FILE'..."
            capture_logs "conda_env_update" conda env update -f "$GANTRY_CONDA_FILE" || return 1
            log_info "Done."
        fi
    elif [[ -f "$GANTRY_CONDA_FILE" ]]; then
        # Create from the environment file.
        log_info "Initializing environment from conda env file '$GANTRY_CONDA_FILE'..."
        capture_logs "conda_env_create" conda env create -n gantry -f "$GANTRY_CONDA_FILE" 
        conda activate gantry &> /dev/null || return 1
        log_info "Done."
    elif [[ -n "$GANTRY_DEFAULT_PYTHON_VERSION" ]]; then
        # Create a new empty environment with the default Python version.
        log_info "Initializing environment with Python $GANTRY_DEFAULT_PYTHON_VERSION..."
        capture_logs "conda_env_create" conda create -y -n gantry "python=$GANTRY_DEFAULT_PYTHON_VERSION" pip
        conda activate gantry &> /dev/null || return 1
        log_info "Done."
    else
        # Create a new empty environment with whatever version of Python conda defaults to.
        log_info "Initializing environment..."
        capture_logs "conda_env_create" conda create -y -n gantry pip
        conda activate gantry &> /dev/null || return 1
        log_info "Done."
    fi

    ensure_pip || return 1

    if [[ -z "$GANTRY_INSTALL_CMD" ]]; then
        if [[ -f 'setup.py' ]] || [[ -f 'pyproject.toml' ]] || [[ -f 'setup.cfg' ]]; then
            log_info "Installing local project..."
            capture_logs "pip_install" pip install . || return 1
            log_info "Done."
        elif [[ -f 'requirements.txt' ]]; then
            log_info "Installing packages from requirements.txt..."
            capture_logs "pip_install" pip install -r requirements.txt || return 1
            log_info "Done."
        fi
    else
        run_custom_cmd "install" "$GANTRY_INSTALL_CMD" || return 1
    fi

    pip freeze > "$GANTRY_DIR/requirements.txt"
}

function setup_python {
    if [[ "$GANTRY_PYTHON_MANAGER" == "uv" ]]; then
        uv_setup_python || return 1
    elif [[ "$GANTRY_PYTHON_MANAGER" == "conda" ]]; then
        conda_setup_python || return 1
    else
        log_error "Unknown python manager '$GANTRY_PYTHON_MANAGER'"
        return 1
    fi
    
    if [[ -z "$PYTHONPATH" ]]; then
        PYTHONPATH="$(pwd)"
    else
        PYTHONPATH="${PYTHONPATH}:$(pwd)"
    fi
    export PYTHONPATH
}

####################################################################################################
########################################## Start setup... ##########################################
####################################################################################################

if [[ -n "$GANTRY_PRE_SETUP_CMD" ]]; then
    log_header "Running custom pre-setup..."
    run_custom_cmd "pre-setup" "$GANTRY_PRE_SETUP_CMD"
fi

######################################
log_header "Validating environment..."
######################################

for env_var in "GANTRY_EXEC_METHOD" "GITHUB_REPO" "GIT_REF" "RESULTS_DIR" "BEAKER_RESULT_DATASET_ID" "BEAKER_NODE_HOSTNAME" "BEAKER_NODE_ID" "BEAKER_ASSIGNED_GPU_COUNT"; do
    if [[ -z "${!env_var+x}" ]]; then
        log_error "Required environment variable '$env_var' is empty"
        exit 1
    fi
done

if [[ -n "$GANTRY_USE_TORCHRUN" ]]; then
    if [[ -z "$BEAKER_ASSIGNED_GPU_COUNT" ]] || ((BEAKER_ASSIGNED_GPU_COUNT < 1)); then
        log_error "'GANTRY_USE_TORCHRUN' (--torchrun) is set but 'BEAKER_ASSIGNED_GPU_COUNT' (--gpus) is not set or less than 1"
        exit 1
    fi
    if is_multi_node_gpu_job; then
        for env_var in "GANTRY_RDZV_ID" "GANTRY_RDZV_PORT"; do
            if [[ -z "${!env_var+x}" ]]; then
                log_error "Required environment variable '$env_var' is empty"
                exit 1
            fi
        done
    fi
fi

# Set PYTHONUNBUFFERED to ensure real-time logging from Python processes.
if [[ -z "$PYTHONUNBUFFERED" ]]; then
    export PYTHONUNBUFFERED=1
fi

log_info "Shell is $(bash --version | head -n 1)."
log_info "Running on Beaker node '${BEAKER_NODE_HOSTNAME}' (${BEAKER_NODE_ID})"
log_physical_host_topology || log_warning "Failed to get physical host topology"
log_info "Results dataset ${RESULTS_DATASET_URL} mounted to '${RESULTS_DIR}'."

log_info "Checking for required tools..."
for tool in "git" "curl"; do
    if ! command -v "$tool" &> /dev/null; then
        log_error "Required tool '$tool' is not installed, please build or use an existing image that comes with '$tool'."
        exit 1
    else
        log_info "Using $($tool --version | head -n 1)."
    fi
done
log_info "Done."

if [[ -n "$GITHUB_TOKEN" ]]; then
    ensure_gh
    # Configure git to use the GitHub CLI as a credential helper so that we can clone private repos.
    # NOTE: this could fail due to race conditions if the user has mounted a host path to the container's '$HOME' directory
    # (it's happened before).
    log_info "Configuring git to use GitHub token for authentication..."
    with_retries 3 capture_logs "setup_gh_auth" gh auth setup-git
    log_info "Done."
fi

# Install cloud credentials if given.
if [[ -n "$GANTRY_AWS_CONFIG" ]]; then
    log_info "Installing AWS config..."
    mkdir -p ~/.aws
    printenv GANTRY_AWS_CONFIG > ~/.aws/config
    log_info "Done."
fi
if [[ -n "$GANTRY_AWS_CREDENTIALS" ]]; then
    log_info "Installing AWS credentials..."
    mkdir -p ~/.aws
    printenv GANTRY_AWS_CREDENTIALS > ~/.aws/credentials
    log_info "Done."
fi
if [[ -n "$GANTRY_GOOGLE_CREDENTIALS" ]]; then
    log_info "Installing Google Cloud credentials..."
    mkdir -p ~/.google
    printenv GANTRY_GOOGLE_CREDENTIALS > ~/.google/credentials.json
    export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.google/credentials.json"
    if command -v gcloud &> /dev/null; then
        ensure_jq
        service_account=$(printenv GANTRY_GOOGLE_CREDENTIALS | jq -r .client_email)
        gcloud auth activate-service-account "$service_account" --key-file="$GOOGLE_APPLICATION_CREDENTIALS"
    else
        log_warning "'gcloud' CLI not found so credentials can't be activated globally. As a result some tools like 'gsutil' may not be able to authenticate."
    fi
    log_info "Done."
fi
if [[ -n "$PYTORCH_KERNEL_CACHE_PATH" ]]; then
    log_info "Creating PyTorch kernel cache directory..."
    mkdir -p "$PYTORCH_KERNEL_CACHE_PATH"
    log_info "Done."
fi

# Configure NCCL variables for the given hardware.
# See https://beaker-docs.apps.allenai.org/experiments/distributed-training.html
if is_multi_node_gpu_job && [[ -z "$GANTRY_SKIP_NCCL_SETUP" ]]; then
    if has_infiniband; then
        log_info "Configuring NCCL for InfiniBand..."
        log_info "You can skip this step by setting the env var 'GANTRY_SKIP_NCCL_SETUP' in your job (--skip-nccl-setup)."
        export NCCL_IB_HCA="^=mlx5_bond_0"
        export NCCL_SOCKET_IFNAME="ib"
        log_info "Done."
    elif [[ -d "/var/lib/tcpxo/lib64" ]]; then
        log_info "Configuring NCCL for GPUDirect-TCPXO..."
        log_info "You can skip this step by setting the env var 'GANTRY_SKIP_NCCL_SETUP' in your job (--skip-nccl-setup)."
        export NCCL_LIB_DIR="/var/lib/tcpxo/lib64"
        export LD_LIBRARY_PATH="/var/lib/tcpxo/lib64:$LD_LIBRARY_PATH"
        # shellcheck disable=SC1091
        source /var/lib/tcpxo/lib64/nccl-env-profile.sh
        export NCCL_PROTO=Simple,LL128
        export NCCL_TUNER_CONFIG_PATH=/var/lib/tcpxo/lib64/a3plus_tuner_config_ll128.textproto
        export NCCL_SHIMNET_GUEST_CONFIG_CHECKER_CONFIG_FILE=/var/lib/tcpxo/lib64/a3plus_guest_config_ll128.textproto
        log_info "Done."
    fi
fi

###################################
log_header "Cloning source code..."
###################################

# Silence detached head warnings.
git config --global advice.detachedHead false

# Initialize empty repo.
capture_logs "git_init" git init
capture_logs "git_remote" git remote add origin "https://github.com/$GITHUB_REPO"

log_info "Cloning source from '$GITHUB_REPO' @ '$GIT_REF'..."
# Shallow clone a single commit. See https://stackoverflow.com/a/43136160
with_retries 5 capture_logs "fetch_repo" git fetch --depth 1 origin "$GIT_REF"
capture_logs "git_checkout" git checkout "$GIT_REF"
log_info "Done."

log_info "Initializing git submodules..."
capture_logs "init_submodules" git submodule update --init --recursive
log_info "Done."

if [[ -z "$GANTRY_NO_PYTHON" ]]; then
    ###################################
    log_header "Building Python env..."
    ###################################
    setup_python
    
    ####################################
    log_header "Python environment info"
    ####################################
    log_info "Using $(python --version) from '$(which python)'."
    if [[ -f "$GANTRY_DIR/requirements.txt" ]]; then
        log_info "Packages:"
        cat "$GANTRY_DIR/requirements.txt"
    fi
elif [[ -n "$GANTRY_INSTALL_CMD" ]]; then
    ######################################
    log_header "Running custom install..."
    ######################################
    run_custom_cmd "install" "$GANTRY_INSTALL_CMD"
fi

if [[ -n "$GANTRY_POST_SETUP_CMD" ]]; then
    #########################################
    log_header "Running custom post-setup..."
    #########################################
    run_custom_cmd "post-setup" "$GANTRY_POST_SETUP_CMD"
fi

if ((BEAKER_ASSIGNED_GPU_COUNT > 0)) && command -v nvidia-smi &> /dev/null; then
    #################################
    log_header "NVIDIA system status"
    #################################
    nvidia-smi
fi

end_time=$(date +%s)
##############################################################################
log_header "Setup complete" "(finished in $((end_time-start_time)) seconds)"
##############################################################################

cmd=()
if [[ -n "$GANTRY_USE_TORCHRUN" ]]; then
    if is_multi_node_gpu_job; then
        cmd+=(
            torchrun
            --nnodes="$BEAKER_REPLICA_COUNT:$BEAKER_REPLICA_COUNT"
            --nproc-per-node="$BEAKER_ASSIGNED_GPU_COUNT"
            --rdzv-id="$GANTRY_RDZV_ID"
            --rdzv-backend=static
            --rdzv-endpoint="$BEAKER_LEADER_REPLICA_HOSTNAME:$GANTRY_RDZV_PORT"
            --node-rank="$BEAKER_REPLICA_RANK"
            --rdzv-conf="read_timeout=420"
        )
    else
        cmd+=(
            torchrun
            --nproc-per-node="$BEAKER_ASSIGNED_GPU_COUNT"
        )
    fi

    # If script isn't a Python file, append `--no-python` option to torchrun command.
    if [[ "$1" != *.py ]]; then
        cmd+=("--no-python")
    fi
fi
cmd+=("$@")

if [[ "$GANTRY_EXEC_METHOD" == "exec" ]]; then
    # exec "$@"
    exec "${cmd[@]}"
elif [[ "$GANTRY_EXEC_METHOD" == "bash" ]]; then
    # bash -c "$*"
    bash -c "${cmd[*]}"
else
    log_error "Unknown value for 'GANTRY_EXEC_METHOD' (--exec-method), got '$GANTRY_EXEC_METHOD'."
    exit 1
fi
