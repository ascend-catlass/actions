#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf -- "${fixture}"' EXIT
mkdir -p "${fixture}/bin" "${fixture}/source" "${fixture}/tmp"
export TEST_LOG="${fixture}/commands" TEST_FILTERED="${fixture}/filtered"
export TMPDIR="${fixture}/tmp" TEST_MINOR=12 TEST_ARCH=x86_64 TEST_FAIL_DOWNLOAD=0
export PATH="${fixture}/bin:${PATH}"
cat > "${fixture}/bin/uname" <<'SH'
#!/usr/bin/env bash
if [[ "$1" == -s ]]; then echo Linux; else echo "${TEST_ARCH}"; fi
SH
cat > "${fixture}/bin/python3" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == --version ]]; then echo "Python 3.${TEST_MINOR}.1"; exit; fi
if [[ "$1" == - ]]; then cat >/dev/null; echo verify >> "${TEST_LOG}"; exit; fi
echo "$3" >> "${TEST_LOG}"
for ((i=1; i<=$#; i++)); do
    arg="${!i}"
    next=$((i+1))
    case "${arg}" in
        --dest) dest="${!next}" ;;
        -r) cp "${!next}" "${TEST_FILTERED}" ;;
        -c) diff "${!next}" <(printf '%s\n' 'torch==2.9.0+cpu' 'torch-npu==2.9.0.post8') ;;
    esac
done
if [[ "$3" == download ]]; then
    [[ "${TEST_FAIL_DOWNLOAD}" == 0 ]] || exit 1
    [[ "$*" == *"cp3${TEST_MINOR}-cp3${TEST_MINOR}-manylinux_2_28_${TEST_ARCH}.whl"* ]]
    touch "${dest}/torch.whl" "${dest}/torch_npu.whl"
fi
SH
chmod +x "${fixture}/bin/"*
printf '%s\n' '# torch comment' torch 'Torch_NPU>=2.9' 'torchvision[extra]' \
    'numpy<=1.24.0' ml_dtypes > "${fixture}/source/requirements.txt"
cp "${fixture}/source/requirements.txt" "${fixture}/original"

for TEST_MINOR in 10 11 12; do
    for TEST_ARCH in x86_64 aarch64; do
        export TEST_MINOR TEST_ARCH
        : > "${TEST_LOG}"
        bash "${repo}/.github/actions/prepare-ci-tests/install-requirements.sh" "${fixture}/source"
        diff "${TEST_LOG}" <(printf '%s\n' download uninstall install install verify)
        diff "${TEST_FILTERED}" <(printf '%s\n' '# torch comment' 'numpy<=1.24.0' ml_dtypes)
        diff "${fixture}/original" "${fixture}/source/requirements.txt"
        [[ -z "$(ls -A "${fixture}/tmp")" ]]
        leftovers=("${fixture}/source/".ci-requirements-*)
        [[ ${#leftovers[@]} == 0 ]]
    done
done
export TEST_FAIL_DOWNLOAD=1
: > "${TEST_LOG}"
if bash "${repo}/.github/actions/prepare-ci-tests/install-requirements.sh" "${fixture}/source"; then
    echo "Expected failed download to stop installation" >&2
    exit 1
fi
diff "${TEST_LOG}" <(printf '%s\n' download)
[[ -z "$(ls -A "${fixture}/tmp")" ]]
echo "Six Python/architecture combinations and download failure checks passed"
