ARG BASE_IMAGE=nvidia/cuda:12.8.1-base-ubuntu22.04

FROM ${BASE_IMAGE}

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       build-essential \
       ca-certificates \
       curl \
       wget \
       libxml2-dev \
       jq \
       git && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL -v -o ~/miniconda.sh -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    chmod +x ~/miniconda.sh && \
    ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    /opt/conda/bin/conda clean -afy && \
    rm -rf /opt/conda/pkgs && \
    curl -sS https://webi.sh/gh | sh && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH /opt/conda/bin:~/.local/bin:$PATH
WORKDIR ~/
ENTRYPOINT ["/bin/bash"]
