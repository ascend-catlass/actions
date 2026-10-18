#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Usage: bash prepare-python.sh CATLASS_SOURCE NEW_VENV" >&2
    exit 2
fi
source_root=$(realpath "$1")
venv=$2
[[ -f "$source_root/python/tla_dsl/requirements.txt" ]] || exit 1
[[ ! -e "$venv" ]] || { echo "Refusing to replace an existing environment: $venv" >&2; exit 1; }
python3 -m venv "$venv"
python="$venv/bin/python"
"$python" -m pip install --upgrade pip
"$python" -m pip install -r "$source_root/python/tla_dsl/requirements.txt"
"$python" -m pip install --group "$source_root/python/tla_dsl/pyproject.toml:cann"
"$python" -m pip install 'torch==2.9.0+cpu' --index-url https://download.pytorch.org/whl/cpu
"$python" -m pip install 'torch_npu==2.9.0.post9' expecttest ml_dtypes
"$python" -m pip freeze > "$venv/requirements-resolved.txt"
