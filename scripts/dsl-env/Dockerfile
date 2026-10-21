ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates clang-19 lld-19 git build-essential python3-dev \
    python3-venv zlib1g-dev libxml2-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/dsl-venv
ENV PATH=/opt/dsl-venv/bin:${PATH}
COPY requirements.txt pyproject.toml /tmp/dsl/
RUN python -m pip install --no-cache-dir 'pip>=25.1' \
    && python -m pip install --no-cache-dir -r /tmp/dsl/requirements.txt \
    && python -m pip install --no-cache-dir --group /tmp/dsl/pyproject.toml:cann \
    && python -m pip install --no-cache-dir 'torch==2.9.0+cpu' --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir 'torch_npu==2.9.0.post9' expecttest ml_dtypes
# pip's negative boolean option uses 0 to select --no-build-isolation.
# Reuse the build tools above; reject missing build requirements immediately.
ENV PIP_NO_BUILD_ISOLATION=0 PIP_CHECK_BUILD_DEPENDENCIES=1
COPY check-python-build.sh /tmp/dsl/check-python-build.sh
RUN --network=none bash /tmp/dsl/check-python-build.sh
RUN python -m pip check \
    && python -m pip freeze > /opt/dsl-venv/requirements-resolved.txt
WORKDIR /workspace/catlass
