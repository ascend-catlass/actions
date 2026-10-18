#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Usage: bash build-image.sh CATLASS_SOURCE IMAGE_TAG" >&2
    exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_root=$(realpath "$1")
context=$(mktemp -d)
trap 'rm -rf -- "$context"' EXIT
cp "$script_dir/Dockerfile" "$context/Dockerfile"
cp "$source_root/python/tla_dsl/requirements.txt" "$source_root/python/tla_dsl/pyproject.toml" "$context/"
docker build --build-arg "BASE_IMAGE=${BASE_IMAGE:-ubuntu:24.04}" -t "$2" "$context"
