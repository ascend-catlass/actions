#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd -P)
manager="${repo_root}/.github/actions/npuir-local-archive/manage-archive.sh"
test_root=$(mktemp -d /tmp/npuir-archive-test.XXXXXX)
cleanup() {
  if [[ $? != 0 && -f "${test_root}/log" ]]; then cat "${test_root}/log" >&2; fi
  case "${test_root}" in /tmp/npuir-archive-test.*) rm -rf -- "${test_root}" ;; esac
}
trap cleanup EXIT
export ARCHIVE_ROOT_INPUT="${test_root}/shared"
export RUNNER_TEMP="${test_root}/runner/_temp"
export GITHUB_OUTPUT="${test_root}/outputs"
export TARGET_ARCH=x86_64 BUILD_CONTRACT=clang19-v1 BUILD_FINGERPRINT=clang-19.1.7
export SOURCE_BRANCH=feature/regbase SOURCE_REF='' LEGACY_POSTFIX='' LEGACY_BUILD_FINGERPRINT=''
export GITHUB_RUN_ID=123 GITHUB_RUN_ATTEMPT=1 GITHUB_SERVER_URL=https://github.com GITHUB_REPOSITORY=test/actions
export SOURCE_PATH=''
mkdir -p "${RUNNER_TEMP}" "${test_root}/seed"
git init -q "${test_root}/seed"
git -C "${test_root}/seed" -c user.name=Test -c user.email=test@example.com commit -q --allow-empty -m seed
export SOURCE_SHA
SOURCE_SHA=$(git -C "${test_root}/seed" rev-parse HEAD)

# Git Bash can exercise filesystem/date behavior using MSYS shortcut symlinks.
# It has no flock; only Linux runs the real lock/concurrency checks below.
native_lock=true
case "$(uname -s)" in
  MINGW*|MSYS*)
    export MSYS=winsymlinks:lnk
    mkdir -p "${test_root}/bin"
    printf '#!/usr/bin/env bash\nexit 0\n' > "${test_root}/bin/flock"
    # Preserve the .lnk extension when MSYS renames a shortcut symlink.
    cat > "${test_root}/bin/mv" <<'SH'
#!/usr/bin/env bash
if [[ "$1" == -Tf && -L "$2" ]]; then
  exec /usr/bin/mv -Tf "$2.lnk" "$3.lnk"
fi
exec /usr/bin/mv "$@"
SH
    chmod +x "${test_root}/bin/flock"
    chmod +x "${test_root}/bin/mv"
    export PATH="${test_root}/bin:${PATH}"
    native_lock=false
    echo 'Git Bash: exercising archive behavior; native flock checks skipped'
    ;;
esac

run_manager() {
  : > "${GITHUB_OUTPUT}"
  bash "${manager}" > "${test_root}/log" 2>&1
}
output() { sed -n "s/^$1=//p" "${GITHUB_OUTPUT}"; }
expect_failure() {
  if run_manager; then echo 'Expected failure' >&2; exit 1; fi
}
fixture() {
  local tree=$1
  mkdir -p "${tree}/build/install/lib/cmake/mlir" "${tree}/build/install/bin"
  cp -a "${test_root}/seed/.git" "${tree}/.git"
  mkdir -p "${tree}/third-party/llvm-project" "${tree}/.git/modules/third-party"
  cp -a "${test_root}/seed/.git" "${tree}/.git/modules/third-party/llvm-project"
  printf 'gitdir: %s\n' "${tree}/.git/modules/third-party/llvm-project" > "${tree}/third-party/llvm-project/.git"
  git config --file "${tree}/.git/modules/third-party/llvm-project/config" core.worktree "${tree}/third-party/llvm-project"
  touch "${tree}/build/install/lib/cmake/mlir/MLIRConfig.cmake"
  printf '#!/bin/sh\nexit 0\n' > "${tree}/build/install/bin/bishengir-opt"
  chmod 700 "${tree}" "${tree}/build/install/bin/bishengir-opt"
}
publish() {
  export BASELINE_DATE=$1 OPERATION=lookup
  run_manager
  [[ "$(output cache_hit)" == false ]]
  SOURCE_PATH=$(output work_path)
  fixture "${SOURCE_PATH}"
  export OPERATION=publish
  run_manager
  [[ "$(output path)" == "${ARCHIVE_ROOT_INPUT}/${BASELINE_DATE}/AscendNPU-IR" ]]
  [[ ! -e "${SOURCE_PATH}" ]]
  [[ "$(git -C "$(output path)/third-party/llvm-project" rev-parse HEAD)" == "${SOURCE_SHA}" ]]
}

publish 20260720
[[ "$(readlink "${ARCHIVE_ROOT_INPUT}/latest")" == 20260720/AscendNPU-IR ]]
[[ -x "${ARCHIVE_ROOT_INPUT}/latest/build/install/bin/bishengir-opt" ]]
if [[ "${native_lock}" == true ]]; then
  [[ "$(stat -c %a "${ARCHIVE_ROOT_INPUT}/latest/build/install/bin/bishengir-opt")" == 755 ]]
fi

publish 20260930
[[ "$(readlink "${ARCHIVE_ROOT_INPUT}/latest")" == 20260930/AscendNPU-IR ]]
publish 20260801
[[ "$(readlink "${ARCHIVE_ROOT_INPUT}/latest")" == 20260930/AscendNPU-IR ]]
export BASELINE_DATE=20260930 OPERATION=lookup
before=$(stat -c %i "${ARCHIVE_ROOT_INPUT}/latest")
run_manager
[[ "$(output cache_hit)" == true ]]
[[ "$(stat -c %i "${ARCHIVE_ROOT_INPUT}/latest")" == "${before}" ]]

# Refuse same-date content conflicts and incomplete builds without changing latest.
original_sha=${SOURCE_SHA}
export SOURCE_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
expect_failure
export SOURCE_SHA=${original_sha} BASELINE_DATE=20261001
run_manager
export SOURCE_PATH
SOURCE_PATH=$(output work_path)
mkdir -p "${SOURCE_PATH}"
export OPERATION=publish
expect_failure
[[ "$(readlink "${ARCHIVE_ROOT_INPUT}/latest")" == 20260930/AscendNPU-IR ]]
export BASELINE_DATE=20260230 OPERATION=lookup
expect_failure

# Migrate both content-keyed and legacy dated runner-local archives.
export BASELINE_DATE=20261002 GITHUB_RUN_ATTEMPT=2
old="${test_root}/runner/_npuir-pipeline/v2-${SOURCE_SHA}-${TARGET_ARCH}-${BUILD_CONTRACT}"
fixture "${old}"
cp "${ARCHIVE_ROOT_INPUT}/20260930/AscendNPU-IR/.npuir-pipeline" "${old}/.npuir-pipeline"
run_manager
[[ "$(output legacy_cache_hit)" == true && -d "${old}" ]]
[[ "$(git -C "$(output path)/third-party/llvm-project" rev-parse HEAD)" == "${SOURCE_SHA}" ]]
[[ "$(readlink "${ARCHIVE_ROOT_INPUT}/latest")" == 20261002/AscendNPU-IR ]]
# Move the old content-keyed fixture aside to test the legacy fallback.
mv "${old}" "${test_root}/old-saved"
export BASELINE_DATE=20261013 LEGACY_POSTFIX=20260930 LEGACY_BUILD_FINGERPRINT=${BUILD_FINGERPRINT}
old="${test_root}/runner/_npuir-pipeline/${LEGACY_POSTFIX}"
fixture "${old}"
printf '%s\n' "SOURCE_SHA=${SOURCE_SHA}" "NPUIR_PIPELINE_POSTFIX=${LEGACY_POSTFIX}" "BUILD_FINGERPRINT=${BUILD_FINGERPRINT}" > "${old}/.npuir-pipeline"
printf 'gitdir: %s\n' "${test_root}/removed-building/.git/modules/third-party/llvm-project" > "${old}/third-party/llvm-project/.git"
ln -s "${old}" "${test_root}/runner/_npuir-pipeline/v2-${SOURCE_SHA}-${TARGET_ARCH}-${BUILD_CONTRACT}"
run_manager
[[ "$(output legacy_cache_hit)" == true ]]
[[ "$(git -C "$(output path)/third-party/llvm-project" rev-parse HEAD)" == "${SOURCE_SHA}" ]]
[[ "$(readlink "${ARCHIVE_ROOT_INPUT}/latest")" == 20261013/AscendNPU-IR ]]

if [[ "${native_lock}" == true ]]; then
  # A lookup must wait while another publisher owns the worker lock.
  exec 8>"${ARCHIVE_ROOT_INPUT}/.publish.lock"
  flock -x 8
  (exec 8>&-; run_manager; touch "${test_root}/lock-completed") &
  waiter=$!
  sleep 0.2
  [[ ! -e "${test_root}/lock-completed" ]]
  flock -u 8
  wait "${waiter}"
  [[ -f "${test_root}/lock-completed" ]]
fi
# Cache reuse can restore a missing latest link, but cannot overwrite a directory.
rm "${ARCHIVE_ROOT_INPUT}/latest"
run_manager
[[ "$(readlink "${ARCHIVE_ROOT_INPUT}/latest")" == 20261013/AscendNPU-IR ]]
rm "${ARCHIVE_ROOT_INPUT}/latest"
mkdir "${ARCHIVE_ROOT_INPUT}/latest"
expect_failure
[[ -d "${ARCHIVE_ROOT_INPUT}/latest" ]]
# Exercise the user-facing migration command with its production build profile.
sed -i 's/^BUILD_FINGERPRINT=.*/BUILD_FINGERPRINT=clang-19.1.7+lld-19.1.7/' "${old}/.npuir-pipeline"
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.longpaths GIT_CONFIG_VALUE_0=true \
  NPUIR_ARCHIVE_ROOT="${test_root}/manual-shared" bash "${repo_root}/scripts/migrate-npuir-cache.sh" \
  "${test_root}/runner/_npuir-pipeline" 20261013 "${original_sha}" 20260930
[[ "$(readlink "${test_root}/manual-shared/latest")" == 20261013/AscendNPU-IR ]]
[[ -d "${old}" ]]
echo 'NPUIR archive tests passed'
