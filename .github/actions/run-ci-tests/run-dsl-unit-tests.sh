#!/usr/bin/env bash
set -eo pipefail

# Use the same toolchain and source package as the upstream IR/Lit jobs.
cd "${RDV_WORKTREE}/python/tla_dsl"
if [[ -z "${ASCEND_HOME_PATH:-}" || ! -f "${ASCEND_HOME_PATH}/set_env.sh" ]]; then
    echo "ASCEND_HOME_PATH must point to the image's CANN toolkit" >&2
    exit 1
fi
source "${ASCEND_HOME_PATH}/set_env.sh"
export BISHENG_COMPILER_PATH="${BISHENG_COMPILER_PATH:-${ASCEND_HOME_PATH}/bin}"
export CATLASS_DSL_PREBUILT_ASCENDNPU_IR="${CATLASS_DSL_PREBUILT_ASCENDNPU_IR:-/opt/AscendNPU-IR}"
export PATH="${CATLASS_DSL_PREBUILT_ASCENDNPU_IR}/build/bin:${CATLASS_DSL_PREBUILT_ASCENDNPU_IR}/build/install/bin:${PATH}"
export PYTHONPATH="${PWD}:${PYTHONPATH:-}"

case "$1" in
    dsl-dev)
        lit_source="${CATLASS_DSL_ASCENDNPU_IR_ROOT:-${CATLASS_DSL_PREBUILT_ASCENDNPU_IR}}/third-party/llvm-project/llvm/utils/lit"
        if [[ ! -f "${lit_source}/lit.py" ]]; then
            echo "LLVM Lit source was not found: ${lit_source}" >&2
            exit 1
        fi
        python -m pip install --no-deps --no-build-isolation --force-reinstall "${lit_source}"
        # Force CMake to run this source version, even if an older llvm-lit
        # executable is present in the image's toolchain bin directory.
        export CMAKE_ARGS="${CMAKE_ARGS:-} -DLLVM_EXTERNAL_LIT=\"${lit_source}/lit.py\""
        bash build.sh
        python -c 'import catlass; print("Dev package:", catlass.__file__)'
        ;;
    dsl-ir)
        python -m pytest -q tests -p no:randomly --durations=20
        ;;
    dsl-lit)
        # This target resolves lit/llvm-lit and FileCheck through upstream CMake.
        cmake --build csrc/mlir/build --target check-tla-lit
        ;;
    *)
        echo "Unknown DSL unit test stage: $1" >&2
        exit 1
        ;;
esac
