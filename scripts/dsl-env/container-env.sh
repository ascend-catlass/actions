#!/usr/bin/env bash
# BASH_ENV for every docker exec bash invocation, including non-DSL tests.
source /opt/dsl-venv/bin/activate
source "${ASCEND_HOME_PATH}/set_env.sh"
export BISHENG_COMPILER_PATH="${ASCEND_HOME_PATH}/bin"
export PATH="${CATLASS_DSL_PREBUILT_ASCENDNPU_IR}/build/bin:${CATLASS_DSL_PREBUILT_ASCENDNPU_IR}/build/install/bin:${PATH}"
export CMAKE_BUILD_PARALLEL_LEVEL=${CMAKE_BUILD_PARALLEL_LEVEL:-32}
if [[ "${CMAKE_ARGS:-}" != *"-DLLVM_EXTERNAL_LIT=/opt/dsl-venv/bin/lit"* ]]; then
    export CMAKE_ARGS="${CMAKE_ARGS:-} -DLLVM_EXTERNAL_LIT=/opt/dsl-venv/bin/lit"
fi
