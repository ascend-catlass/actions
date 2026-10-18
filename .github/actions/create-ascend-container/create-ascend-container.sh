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

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
env_scripts="${repo_root}/scripts/dsl-env"
cann=$(dirname -- "$(realpath -- "${CANN_ROOT:-/opt/cann_weekly/latest/ascend-toolkit}/set_env.sh")")
npuir=$(realpath -- "${NPUIR_ROOT:-/opt/AscendNPU-IR/latest/AscendNPU-IR}")
[[ -f "$cann/set_env.sh" && -f "$npuir/.npuir-pipeline" ]] || {
    echo '::error::Provision weekly CANN and matching NPUIR before testing.' >&2
    exit 1
}
image="${CANN_REPO}:${CANN_TAG}"
# Serialize only image creation. Recheck after acquiring the lock so parallel
# jobs never build the same missing image twice.
bash "$env_scripts/ensure-image.sh" "$HOST_WORKTREE" "$image"

args=(
    --detach --init --privileged --name "${NAME}"
    --mount "type=bind,source=${HOST_WORKTREE},target=${CONTAINER_WORKTREE}"
    --workdir "${CONTAINER_WORKTREE}"
    --mount "type=bind,source=$cann,target=$cann,readonly"
    --mount "type=bind,source=$npuir,target=$npuir,readonly"
    --mount "type=bind,source=$env_scripts/container-env.sh,target=/opt/catlass-ci-env.sh,readonly"
    --mount "type=bind,source=$env_scripts/run.sh,target=/opt/catlass-env-run.sh,readonly"
    --env "ASCEND_HOME_PATH=$cann"
    --env "CATLASS_DSL_PREBUILT_ASCENDNPU_IR=$npuir"
    --env BASH_ENV=/opt/catlass-ci-env.sh
)
for driver_path in \
    /usr/local/dcmi \
    /usr/local/bin/npu-smi \
    /usr/local/Ascend/driver \
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
docker run "${args[@]}" "$image" bash -c 'exec sleep infinity'
# Validate the mounted compiler archive against this checkout before any test.
docker exec "$NAME" bash /opt/catlass-env-run.sh "$CONTAINER_WORKTREE" \
    /opt/dsl-venv "$cann" "$npuir" -- python -c \
    'import acl, torch, torch_npu; print("CANN:", __import__("os").environ["ASCEND_HOME_PATH"]); print("PyTorch:", torch.__version__, "TorchNPU:", torch_npu.__version__)'
echo "Weekly CANN read-only mount: $cann"
echo "NPUIR read-only mount: $npuir"
echo "worktree=${CONTAINER_WORKTREE}" >> "${GITHUB_OUTPUT}"
