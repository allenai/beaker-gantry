ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

# This label communicates to the NVIDIA Container Runtime that this
# container needs the NVIDIA driver mounted from the host.
LABEL com.nvidia.volumes.needed="nvidia_driver"

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    DEBIAN_FRONTEND="noninteractive" \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Add NVIDIA driver libs + CUDA libs, keep anything that was there before.
ENV LD_LIBRARY_PATH=/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64:/usr/local/cuda/lib

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        wget \
        libxml2-dev \
        jq \
        git \
    && apt-get autoremove -y \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh --no-install-recommends \
    && apt-get autoremove -y \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

# Install miniconda
RUN curl -fsSL -v -o ~/miniconda.sh -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && chmod +x ~/miniconda.sh \
    && ~/miniconda.sh -b -p /opt/conda \
    && rm ~/miniconda.sh \
    && /opt/conda/bin/conda clean -afy \
    && rm -rf /opt/conda/pkgs
ENV PATH=/opt/conda/bin:$PATH

# Install uv and uvx
# uv will default to using conda's python executable at /opt/miniconda3/bin/python
# https://docs.astral.sh/uv/concepts/python-versions/#discovery-of-python-versions
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace

ENTRYPOINT ["/bin/bash"]
