#!/usr/bin/env bash
# Run a command using separately provisioned Python, CANN and NPUIR trees.
set -eo pipefail
if [[ $# -lt 6 || "$5" != -- ]]; then
    echo "Usage: bash run.sh CATLASS VENV CANN NPUIR -- COMMAND [ARGS...]" >&2
    exit 2
fi
source_root=$(realpath "$1")
venv=$(realpath "$2")
cann=$(realpath "$3")
npuir=$(realpath "$4")
shift 5
for file in "$venv/bin/activate" "$cann/set_env.sh" \
    "$npuir/build/install/lib/cmake/mlir/MLIRConfig.cmake" \
    "$npuir/build/install/lib/cmake/llvm/LLVMConfig.cmake" \
    "$npuir/third-party/llvm-project/mlir/CMakeLists.txt" "$npuir/.npuir-pipeline"; do
    [[ -f "$file" ]] || { echo "Missing environment file: $file" >&2; exit 1; }
done
expected_sha=${CATLASS_DSL_EXPECTED_NPUIR_SHA:-}
if [[ -z "$expected_sha" ]]; then
    expected_sha=$(git -c safe.directory="$source_root" -C "$source_root" ls-tree HEAD python/tla_dsl/3rdparty/AscendNPU-IR | awk '$1 == "160000" && $2 == "commit" {print $3}')
fi
actual_sha=$(sed -n 's/^SOURCE_SHA=//p' "$npuir/.npuir-pipeline")
contract=$(sed -n 's/^BUILD_CONTRACT=//p' "$npuir/.npuir-pipeline")
archive_arch=$(sed -n 's/^TARGET_ARCH=//p' "$npuir/.npuir-pipeline")
if [[ ! "$expected_sha" =~ ^[0-9a-f]{40}$ || "$actual_sha" != "$expected_sha" ||
      "$archive_arch" != "$(uname -m)" ||
      "$contract" != clang19-lld19-release-rtti-assert-triton-zstd-off-v1 ]]; then
    echo "NPUIR archive does not match the source revision, architecture or build contract." >&2
    exit 1
fi
source "$venv/bin/activate"
source "$cann/set_env.sh"
export CATLASS_DSL_PREBUILT_ASCENDNPU_IR="$npuir"
export CATLASS_DSL_ASCENDNPU_IR_ROOT="$npuir"
export CATLASS_DSL_ASCENDNPU_IR_INSTALL_DIR="$npuir/build/install"
export BISHENG_COMPILER_PATH="$ASCEND_HOME_PATH/bin"
export PATH="$npuir/build/bin:$npuir/build/install/bin:$PATH"
export CMAKE_BUILD_PARALLEL_LEVEL=${CMAKE_BUILD_PARALLEL_LEVEL:-32}
# The archive's llvm-lit shebang belongs to its producer container.
export CMAKE_ARGS="${CMAKE_ARGS:-} -DLLVM_EXTERNAL_LIT=\"$venv/bin/lit\""
cd "$source_root"
exec "$@"
