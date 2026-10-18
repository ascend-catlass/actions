#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 6 || "$5" != -- ]]; then
    echo "Usage: bash run-container.sh CATLASS IMAGE CANN NPUIR -- COMMAND [ARGS...]" >&2
    exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_root=$(realpath "$1")
image=$2
# ascend-toolkit can be a directory of symlinks into a sibling cann-X.Y tree.
cann=$(dirname -- "$(realpath -- "$3/set_env.sh")")
npuir=$(realpath "$4")
shift 5
[[ -d "$source_root/python/tla_dsl" && "$image" != -* && -n "$image" ]] || exit 1
args=(--rm --init --privileged
    --mount "type=bind,source=$source_root,target=/workspace/catlass"
    --mount "type=bind,source=$cann,target=$cann,readonly"
    --mount "type=bind,source=$npuir,target=$npuir,readonly"
    --mount "type=bind,source=$script_dir/run.sh,target=/usr/local/bin/catlass-env-run,readonly")
for path in /usr/local/Ascend/driver /usr/local/dcmi /usr/local/bin/npu-smi /etc/ascend_install.info; do
    [[ -e "$path" ]] || { echo "Missing Ascend driver path: $path" >&2; exit 1; }
    args+=(--mount "type=bind,source=$path,target=$path,readonly")
done
if [[ -n "${CATLASS_DSL_EXPECTED_NPUIR_SHA:-}" ]]; then
    args+=(-e "CATLASS_DSL_EXPECTED_NPUIR_SHA=$CATLASS_DSL_EXPECTED_NPUIR_SHA")
fi
args+=(-e "CMAKE_BUILD_PARALLEL_LEVEL=${CMAKE_BUILD_PARALLEL_LEVEL:-32}")
docker run "${args[@]}" "$image" bash /usr/local/bin/catlass-env-run \
    /workspace/catlass /opt/dsl-venv "$cann" "$npuir" -- "$@"
