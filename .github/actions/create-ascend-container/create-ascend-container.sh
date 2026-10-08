#!/usr/bin/env bash
set -euo pipefail

# Container runners already have the image environment and device mappings.
if [[ -f /.dockerenv ]]; then
    echo "Already inside a container; using the current environment."
    {
        echo "container-name="
        echo "worktree=${HOST_WORKTREE}"
    } >> "${GITHUB_OUTPUT}"
    exit 0
fi

if [[ ! "${NAME}" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]+$ ]]; then
    echo "::error::Invalid Docker container name: ${NAME}"
    exit 1
fi
if [[ -z "${CANN_REPO}" || -z "${CANN_TAG}" ]]; then
    echo "::error::image-repository and image-tag must be nonempty."
    exit 1
fi
if [[ ! -d "${HOST_WORKTREE}" || "${HOST_WORKTREE}" != /* ||
      "${CONTAINER_WORKTREE}" != /* ]]; then
    echo "::error::worktree must be an existing absolute directory; container-worktree must be absolute."
    exit 1
fi

docker info >/dev/null
if docker container inspect "${NAME}" >/dev/null 2>&1; then
    echo "::error::Container ${NAME} already exists; choose a unique name."
    exit 1
fi

args=(
    --detach --init --privileged --name "${NAME}"
    --mount "type=bind,source=${HOST_WORKTREE},target=${CONTAINER_WORKTREE}"
    --workdir "${CONTAINER_WORKTREE}"
)
for driver_path in \
    /usr/local/dcmi \
    /usr/local/bin/npu-smi \
    /usr/local/Ascend/driver/lib64 \
    /usr/local/Ascend/driver/version.info \
    /etc/ascend_install.info; do
    if [[ ! -e "${driver_path}" ]]; then
        echo "::error::Required Ascend driver path is missing: ${driver_path}"
        exit 1
    fi
    args+=(--mount "type=bind,source=${driver_path},target=${driver_path},readonly")
done

# Publish the name before starting so an always() cleanup step can also remove
# a container that Docker created but failed to start. Existing containers were
# rejected above, so only this action's container is eligible for cleanup.
echo "container-name=${NAME}" >> "${GITHUB_OUTPUT}"
docker run "${args[@]}" "${CANN_REPO}:${CANN_TAG}" bash -c 'exec sleep infinity'
echo "worktree=${CONTAINER_WORKTREE}" >> "${GITHUB_OUTPUT}"
