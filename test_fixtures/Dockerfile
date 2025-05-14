FROM ubuntu:latest

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ARG DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       build-essential \
       ca-certificates \
       curl \
       wget \
       libxml2-dev \
       jq \
       git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENTRYPOINT ["/bin/bash"]
