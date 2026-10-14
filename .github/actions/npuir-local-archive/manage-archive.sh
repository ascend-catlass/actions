#!/usr/bin/env bash
set -euo pipefail
umask 022

fail() { echo "::error::$*" >&2; exit 1; }
manifest_value() { sed -n "s/^$1=//p" "$2"; }

[[ "${OPERATION}" == lookup || "${OPERATION}" == publish ]] || fail 'operation must be lookup or publish'
[[ "${SOURCE_SHA}" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid source_sha: ${SOURCE_SHA}"
[[ "${TARGET_ARCH}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$ ]] || fail "Invalid target_arch: ${TARGET_ARCH}"
[[ "${BUILD_CONTRACT}" =~ ^[A-Za-z0-9][A-Za-z0-9._+-]{0,95}$ ]] || fail "Invalid build_contract: ${BUILD_CONTRACT}"
[[ "${BASELINE_DATE}" =~ ^[0-9]{8}$ ]] || fail 'baseline_date must be YYYYMMDD'
parsed_date=$(date -d "${BASELINE_DATE:0:4}-${BASELINE_DATE:4:2}-${BASELINE_DATE:6:2}" +%Y%m%d) || fail 'Invalid calendar date'
[[ "${parsed_date}" == "${BASELINE_DATE}" ]] || fail 'Invalid calendar date'
[[ -z "${BUILD_FINGERPRINT}" || "${BUILD_FINGERPRINT}" =~ ^[A-Za-z0-9][A-Za-z0-9._+:-]{0,127}$ ]] || fail 'Invalid build_fingerprint'
[[ -z "${LEGACY_POSTFIX}" || "${LEGACY_POSTFIX}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || fail 'Invalid legacy_postfix'

archive_root=${ARCHIVE_ROOT_INPUT:-/opt/AscendNPU-IR}
[[ "${archive_root}" == /* && "${archive_root}" != / ]] || fail 'archive_root must be an absolute non-root path'
# Only the default system directory is provisioned with elevated privileges.
if [[ ! -d "${archive_root}" ]]; then
  if [[ "${archive_root}" == /opt/AscendNPU-IR && ! -w /opt ]]; then
    sudo -n install -d -m 0755 -o "$(id -u)" -g "$(id -g)" "${archive_root}"
  else
    mkdir -p "${archive_root}"
  fi
fi
[[ -w "${archive_root}" ]] || fail "Runner needs write access to ${archive_root}"
archive_root=$(cd "${archive_root}" && pwd -P)
archive_key="v2-${SOURCE_SHA}-${TARGET_ARCH}-${BUILD_CONTRACT}"
archive_path="${archive_root}/${BASELINE_DATE}/AscendNPU-IR"
work_path="${archive_root}/.building-${archive_key}-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
{
  echo "archive_key=${archive_key}"
  echo "path=${archive_path}"
  echo "work_path=${work_path}"
} >> "${GITHUB_OUTPUT}"

# Serialize publication, migration, and latest comparison on the worker, even
# across different workflows or source commits. Builds do not hold this lock.
exec 9>"${archive_root}/.publish.lock"
flock -x 9
[[ ! -L "${archive_root}/${BASELINE_DATE}" ]] || fail 'Dated directory must not be a symlink'

validate_archive() {
  local tree=$1 legacy=${2:-false} manifest stored_sha stored_fingerprint
  manifest="${tree}/.npuir-pipeline"
  [[ -f "${manifest}" && -f "${tree}/build/install/lib/cmake/mlir/MLIRConfig.cmake" ]] || fail "Incomplete NPUIR archive: ${tree}"
  stored_sha=$(manifest_value SOURCE_SHA "${manifest}")
  stored_fingerprint=$(manifest_value BUILD_FINGERPRINT "${manifest}")
  [[ "${stored_sha}" == "${SOURCE_SHA}" ]] || fail "Date ${BASELINE_DATE} conflicts with source commit ${stored_sha} at ${tree}"
  if [[ "${legacy}" == true ]]; then
    [[ "$(manifest_value NPUIR_PIPELINE_POSTFIX "${manifest}")" == "${LEGACY_POSTFIX}" ]] || fail 'Legacy archive suffix mismatch'
    [[ -z "${LEGACY_BUILD_FINGERPRINT}" || "${stored_fingerprint}" == "${LEGACY_BUILD_FINGERPRINT}" ]] || fail 'Legacy build fingerprint mismatch'
  else
    [[ "$(manifest_value ARCHIVE_KEY "${manifest}")" == "${archive_key}" &&
       "$(manifest_value TARGET_ARCH "${manifest}")" == "${TARGET_ARCH}" &&
       "$(manifest_value BUILD_CONTRACT "${manifest}")" == "${BUILD_CONTRACT}" ]] || fail "Archive manifest does not match ${archive_key}"
  fi
  [[ -z "${BUILD_FINGERPRINT}" || "${stored_fingerprint}" == "${BUILD_FINGERPRINT}" ]] || fail 'Build fingerprint mismatch'
}

write_manifest() {
  local tree=$1 previous="${1}/.npuir-pipeline" branch=${SOURCE_BRANCH} ref=${SOURCE_REF}
  local fingerprint=${BUILD_FINGERPRINT} built_at producer
  built_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
  producer="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
  if [[ -f "${previous}" ]]; then
    branch=$(manifest_value SOURCE_BRANCH "${previous}")
    ref=$(manifest_value SOURCE_REF "${previous}")
    fingerprint=$(manifest_value BUILD_FINGERPRINT "${previous}")
    built_at=$(manifest_value BUILT_AT "${previous}")
    producer=$(manifest_value PRODUCER_RUN "${previous}")
  fi
  {
    echo 'SCHEMA_VERSION=2'
    echo "ARCHIVE_KEY=${archive_key}"
    echo "SOURCE_SHA=${SOURCE_SHA}"
    echo "SOURCE_BRANCH=${branch}"
    echo "SOURCE_REF=${ref}"
    echo "TARGET_ARCH=${TARGET_ARCH}"
    echo "BUILD_CONTRACT=${BUILD_CONTRACT}"
    echo "BASELINE_DATE=${BASELINE_DATE}"
    echo "BUILD_FINGERPRINT=${fingerprint}"
    echo "BUILT_AT=${built_at}"
    echo "PRODUCER_RUN=${producer}"
  } > "${tree}/.npuir-pipeline"
}

update_latest() {
  local latest="${archive_root}/latest" current target current_date temporary current_tree
  local link_date=${BASELINE_DATE}
  if [[ -L "${latest}" ]]; then
    current=$(readlink -f "${latest}") || fail 'latest is a dangling symlink'
    target=${current#"${archive_root}/"}
    [[ "${target}" =~ ^([0-9]{8})(/AscendNPU-IR)?$ ]] || fail "Unexpected latest target: ${current}"
    current_date=${BASH_REMATCH[1]}
    current_tree="${archive_root}/${current_date}/AscendNPU-IR"
    [[ -f "${current_tree}/.npuir-pipeline" && -f "${current_tree}/build/install/lib/cmake/mlir/MLIRConfig.cmake" ]] || fail 'latest points to an incomplete archive'
    [[ "$(manifest_value BASELINE_DATE "${current_tree}/.npuir-pipeline")" == "${current_date}" ]] || fail 'latest date does not match its manifest'
    if [[ "${BASELINE_DATE}" < "${current_date}" || "${BASELINE_DATE}" == "${current_date}" ]]; then
      if [[ "${target}" == "${current_date}" ]]; then
        echo "Keeping latest at ${current_date}"
        return
      fi
      # Repair the previous nested link without rolling its version back.
      link_date=${current_date}
    fi
  elif [[ -e "${latest}" ]]; then
    fail "latest exists and is not a symlink: ${latest}"
  fi
  temporary="${archive_root}/.latest-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"
  [[ ! -e "${temporary}" && ! -L "${temporary}" ]] || fail "Temporary latest link already exists: ${temporary}"
  ln -s "${link_date}" "${temporary}"
  mv -Tf "${temporary}" "${latest}"
  echo "Updated latest -> ${link_date}"
}

publish_tree() {
  local tree=$1 original=${2:-$1} git_file git_dir relative
  [[ ! -e "${archive_path}" && ! -L "${archive_path}" ]] || fail "Archive already exists: ${archive_path}"
  # The LLVM checkout uses --separate-git-dir with an absolute path. Make
  # submodule Git pointers relative before moving/copying the complete tree.
  while IFS= read -r -d '' git_file; do
    git_dir=$(sed -n 's/^gitdir: //p' "${git_file}")
    if [[ "${git_dir}" == "${original}/.git/"* ]]; then
      git_dir="${tree}${git_dir#"${original}"}"
    elif [[ "${git_dir}" == /*/.git/modules/* ]]; then
      # Older publishers moved .building-* without updating LLVM's absolute
      # gitfile. Its Git directory was moved along with the complete tree.
      git_dir="${tree}/.git/modules/${git_dir#*/.git/modules/}"
    elif [[ "${git_dir}" != /* ]]; then
      git_dir=$(realpath -m "${git_file%/*}/${git_dir}")
    fi
    git_dir=$(realpath -m "${git_dir}")
    [[ "${git_dir}" == "${tree}/.git/"* ]] || fail "Submodule Git directory is outside the archive: ${git_file}"
    [[ -f "${git_dir}/config" ]] || fail "Missing submodule Git config: ${git_dir}"
    relative=$(realpath --relative-to="${git_file%/*}" "${git_dir}")
    printf 'gitdir: %s\n' "${relative}" > "${git_file}"
    relative=$(realpath --relative-to="${git_dir}" "${git_file%/*}")
    git config --file "${git_dir}/config" core.worktree "${relative}"
  done < <(find "${tree}" -path "${tree}/.git" -prune -o -type f -name .git -print0)
  # Preserve executable bits and grant all local users read/traverse access.
  chmod -R a+rX "${tree}"
  mkdir -p "${archive_root}/${BASELINE_DATE}"
  chmod a+rx "${archive_root}" "${archive_root}/${BASELINE_DATE}"
  mv -T "${tree}" "${archive_path}"
}

cache_hit=false
legacy_cache_hit=false
if [[ "${OPERATION}" == lookup ]]; then
  if [[ -e "${archive_path}" || -L "${archive_path}" ]]; then
    [[ ! -L "${archive_path}" ]] || fail 'Dated archive must be a real directory'
    validate_archive "${archive_path}"
    [[ "$(manifest_value BASELINE_DATE "${archive_path}/.npuir-pipeline")" == "${BASELINE_DATE}" ]] || fail 'Archive date mismatch'
    cache_hit=true
  else
    # Keep original caches intact for running consumers and pipeline rollback.
    runner_work_root=$(cd "${RUNNER_TEMP}/.." && pwd -P)
    old_root="${runner_work_root}/_npuir-pipeline"
    candidate="${old_root}/${archive_key}"
    legacy=false
    if [[ -L "${candidate}" ]]; then
      [[ -n "${LEGACY_POSTFIX}" && "$(readlink -f "${candidate}")" == "${old_root}/${LEGACY_POSTFIX}" ]] || fail 'Unexpected old archive symlink'
      legacy=true
    elif [[ ! -e "${candidate}" && -n "${LEGACY_POSTFIX}" ]]; then
      candidate="${old_root}/${LEGACY_POSTFIX}"
      legacy=true
    fi
    if [[ -e "${candidate}" ]]; then
      # A legacy date cache may hold a different gitlink; build the requested
      # commit in that case, as in the previous archive protocol.
      if [[ "${legacy}" != true || "$(manifest_value SOURCE_SHA "${candidate}/.npuir-pipeline")" == "${SOURCE_SHA}" ]]; then
        validate_archive "${candidate}" "${legacy}"
        candidate=$(cd "${candidate}" && pwd -P)
        [[ ! -e "${work_path}" && ! -L "${work_path}" ]] || fail "Work path already exists: ${work_path}"
        cp -a "${candidate}/." "${work_path}"
        write_manifest "${work_path}"
        publish_tree "${work_path}" "${candidate}"
        cache_hit=true
        legacy_cache_hit=true
        echo "Migrated ${candidate} to ${archive_path}"
      fi
    fi
  fi
  if [[ "${cache_hit}" != true ]]; then
    printf '%s\n' 'cache_hit=false' 'legacy_cache_hit=false' >> "${GITHUB_OUTPUT}"
    exit 0
  fi
else
  [[ "${SOURCE_PATH}" == "${work_path}" ]] || fail "source_path must equal ${work_path}"
  [[ ! -L "${SOURCE_PATH}" && -f "${SOURCE_PATH}/build/install/lib/cmake/mlir/MLIRConfig.cmake" ]] || fail "Build is incomplete: ${SOURCE_PATH}"
  [[ "$(git -C "${SOURCE_PATH}" rev-parse HEAD)" == "${SOURCE_SHA}" ]] || fail 'Build source commit mismatch'
  write_manifest "${SOURCE_PATH}"
  publish_tree "${SOURCE_PATH}"
fi

update_latest
{
  echo "cache_hit=${cache_hit}"
  echo "legacy_cache_hit=${legacy_cache_hit}"
  echo "source_sha=${SOURCE_SHA}"
  echo "target_arch=${TARGET_ARCH}"
  echo "build_contract=${BUILD_CONTRACT}"
  echo "baseline_date=${BASELINE_DATE}"
  echo "build_fingerprint=$(manifest_value BUILD_FINGERPRINT "${archive_path}/.npuir-pipeline")"
} >> "${GITHUB_OUTPUT}"
echo "Selected shared NPUIR archive: ${archive_path}"
