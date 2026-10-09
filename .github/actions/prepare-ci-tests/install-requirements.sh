#!/usr/bin/env bash
set -euo pipefail

cd "${1:?Source worktree is required}"
[[ -f requirements.txt ]] || { echo "Missing requirements.txt" >&2; exit 1; }
[[ "$(uname -s)" == Linux ]] || { echo "Linux is required" >&2; exit 1; }

python_version="$(python3 --version)"
case "${python_version}" in
    'Python 3.10.'*) python_tag=cp310 ;;
    'Python 3.11.'*) python_tag=cp311 ;;
    'Python 3.12.'*) python_tag=cp312 ;;
    *) echo "Unsupported Python: ${python_version}" >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64 | amd64) arch=x86_64 ;;
    aarch64 | arm64) arch=aarch64 ;;
    *) echo "Unsupported CPU architecture" >&2; exit 1 ;;
esac

pypi_mirror=https://mirror.nju.edu.cn/pypi/web/simple
torch_wheel="https://mirror.nju.edu.cn/pytorch/whl/cpu/torch-2.9.0%2Bcpu-${python_tag}-${python_tag}-manylinux_2_28_${arch}.whl"
download_dir=""
filtered_requirements=""
cleanup() {
    [[ -z "${download_dir}" ]] || rm -rf -- "${download_dir}"
    [[ -z "${filtered_requirements}" ]] || rm -f -- "${filtered_requirements}"
}
trap cleanup EXIT
download_dir="$(mktemp -d)"
# Keep relative requirement paths relative to the original requirements.txt.
filtered_requirements="$(mktemp "${PWD}/.ci-requirements-XXXXXX")"
awk 'tolower($0) !~ /^[[:space:]]*torch[[:alnum:]_.-]*(\[|[[:space:]<>=!~@;]|$)/' \
    requirements.txt > "${filtered_requirements}"
constraints="${download_dir}/constraints.txt"
printf '%s\n' 'torch==2.9.0+cpu' 'torch-npu==2.9.0.post8' > "${constraints}"

# Download the matching pair before removing the installed packages.
echo "Installing CPU Torch from ${torch_wheel}"
python3 -m pip download --no-deps --only-binary=:all: \
    --index-url "${pypi_mirror}" --dest "${download_dir}" \
    "${torch_wheel}" torch-npu==2.9.0.post8
shopt -s nullglob
wheels=("${download_dir}"/*.whl)
[[ ${#wheels[@]} == 2 ]] || { echo "Expected two Torch wheels" >&2; exit 1; }
python3 -m pip uninstall -y torch torch-npu
python3 -m pip install --index-url "${pypi_mirror}" -c "${constraints}" "${wheels[@]}"
python3 -m pip install --index-url "${pypi_mirror}" -c "${constraints}" -r "${filtered_requirements}"

python3 - <<'PY'
import torch
from importlib.metadata import version

assert torch.__version__ == "2.9.0+cpu", torch.__version__
assert torch.version.cuda is None, torch.version.cuda
assert version("torch-npu") == "2.9.0.post8", version("torch-npu")
print("Verified torch=2.9.0+cpu, torch-npu=2.9.0.post8, CUDA=None")
PY
