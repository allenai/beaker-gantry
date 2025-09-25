# See https://hub.docker.com/r/nvidia/cuda/tags?name=-base-ubuntu22 for good defaults
ARG UBUNTU_VERSION=22.04
ARG TARGET_PLATFORM=x86_64
ARG CUDA_VERSION=12.8.1
ARG BASE_IMAGE=nvidia/cuda:${CUDA_VERSION}-base-ubuntu${UBUNTU_VERSION}

FROM ${BASE_IMAGE}

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       ca-certificates \
       curl \
       unzip \
       wget \
       libxml2-dev \
       jq \
       cmake \
       git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -v -o ~/miniconda.sh -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && chmod +x ~/miniconda.sh \
    && ~/miniconda.sh -b -p /opt/conda \
    && rm ~/miniconda.sh \
    && /opt/conda/bin/conda clean -afy \
    && rm -rf /opt/conda/pkgs \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && curl -sS https://webi.sh/gh | sh \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm awscliv2.zip \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" \
        | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
        | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
    && apt-get update -y \
    && apt-get install google-cloud-sdk -y \
    && rm -rf /var/lib/apt/lists/*

# Install MLNX OFED user-space drivers for InfiniBand.
# See https://docs.nvidia.com/networking/pages/releaseview.action?pageId=15049785#Howto:DeployRDMAacceleratedDockercontaineroverInfiniBandfabric.-Dockerfile
ARG UBUNTU_VERSION
ARG TARGET_PLATFORM
ENV MOFED_VER="24.01-0.3.3.1"
RUN wget --quiet https://content.mellanox.com/ofed/MLNX_OFED-${MOFED_VER}/MLNX_OFED_LINUX-${MOFED_VER}-ubuntu${UBUNTU_VERSION}-${TARGET_PLATFORM}.tgz && \
    tar -xvf MLNX_OFED_LINUX-${MOFED_VER}-ubuntu${UBUNTU_VERSION}-${TARGET_PLATFORM}.tgz && \
    MLNX_OFED_LINUX-${MOFED_VER}-ubuntu${UBUNTU_VERSION}-${TARGET_PLATFORM}/mlnxofedinstall --basic --user-space-only --without-fw-update -q && \
    rm -rf MLNX_OFED_LINUX-${MOFED_VER}-ubuntu${UBUNTU_VERSION}-${TARGET_PLATFORM} && \
    rm MLNX_OFED_LINUX-${MOFED_VER}-ubuntu${UBUNTU_VERSION}-${TARGET_PLATFORM}.tgz

ENV PATH=/opt/conda/bin:~/.local/bin:$PATH
WORKDIR ~/
ENTRYPOINT ["/bin/bash"]
