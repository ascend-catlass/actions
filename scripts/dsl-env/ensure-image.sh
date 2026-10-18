#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Usage: bash ensure-image.sh CATLASS_SOURCE IMAGE_TAG" >&2
    exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image_key=$(printf '%s' "$2" | sha256sum | cut -d ' ' -f 1)
lock_root=${RUNNER_TEMP:-${TMPDIR:-/var/tmp}}
mkdir -p "$lock_root"
(
    flock 9
    if ! docker image inspect "$2" >/dev/null 2>&1; then
        echo "Image $2 is missing; building the lightweight environment now."
        TMPDIR="$lock_root" bash "$script_dir/build-image.sh" "$1" "$2"
    fi
) 9> "$lock_root/catlass-image-${image_key}.lock"
