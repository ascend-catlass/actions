#!/usr/bin/env bash
# Run as the CI runner account from an updated actions checkout.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 4 ]]; then
  echo "Usage: bash $0 OLD_CACHE_ROOT [VERSION_DATE [SOURCE_SHA [LEGACY_POSTFIX]]]" >&2
  exit 1
fi
repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
old_root=$(cd "$1" && pwd -P)
[[ "${old_root##*/}" == _npuir-pipeline ]] || {
  echo 'OLD_CACHE_ROOT must be the previous _npuir-pipeline directory' >&2
  exit 1
}

export OPERATION=lookup
export ARCHIVE_ROOT_INPUT=${NPUIR_ARCHIVE_ROOT:-/opt/AscendNPU-IR}
export BASELINE_DATE=${2:-20261013}
export SOURCE_SHA=${3:-693abf31f3d88d13d30d9578fcf6513b90c0ee33}
export LEGACY_POSTFIX=${4:-20260930}
export TARGET_ARCH
TARGET_ARCH=$(uname -m)
export BUILD_CONTRACT=clang19-lld19-release-rtti-assert-triton-zstd-off-v1
export BUILD_FINGERPRINT=clang-19.1.7+lld-19.1.7
export LEGACY_BUILD_FINGERPRINT=${BUILD_FINGERPRINT}
export SOURCE_PATH='' SOURCE_BRANCH=feature/regbase SOURCE_REF=${SOURCE_SHA}
export RUNNER_TEMP="${old_root%/*}/_temp"
[[ -d "${RUNNER_TEMP}" ]] || {
  echo "Runner temp directory does not exist: ${RUNNER_TEMP}" >&2
  exit 1
}
export GITHUB_RUN_ID="manual-$(date +%s)-$$" GITHUB_RUN_ATTEMPT=1
export GITHUB_SERVER_URL=https://github.com GITHUB_REPOSITORY=ascend-catlass/actions
export GITHUB_OUTPUT
GITHUB_OUTPUT=$(mktemp)
trap 'rm -f -- "${GITHUB_OUTPUT}"' EXIT

bash "${repo_root}/.github/actions/npuir-local-archive/manage-archive.sh"
if ! grep -qx 'cache_hit=true' "${GITHUB_OUTPUT}"; then
  echo "No completed cache matching ${SOURCE_SHA} (${TARGET_ARCH}) found in ${old_root}; nothing migrated." >&2
  exit 1
fi
echo "Migration complete: ${ARCHIVE_ROOT_INPUT}/${BASELINE_DATE}/AscendNPU-IR"
echo "latest -> $(readlink "${ARCHIVE_ROOT_INPUT}/latest")"
