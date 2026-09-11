#!/usr/bin/env bash

set -eo pipefail

# Hotfix (2026-09-10, re-applied 2026-09-11): strip libfaketime injection before
# running NPU tests. The Ascend driver/runtime is intolerant of faked clocks —
# relative timeouts hijacked by FAKETIME cause event-wait mismatches, host
# double-frees (rtFreeHost) and post-suite hangs. Wall-clock compensation is
# only needed by the Listener/Worker chain, not the test process tree.
unset LD_PRELOAD FAKETIME FAKETIME_SHARED FAKETIME_DONT_FAKE_MONOTONIC

# Hard timeout so any unknown hang cannot consume the full 90-minute platform limit.
TEST_HARD_TIMEOUT=${TEST_HARD_TIMEOUT:-3600}

CANN_VERSION="9.1.0"

if [[ ! -d "${RDV_WORKTREE}" ]]; then
    echo "CATLASS worktree does not exist: ${RDV_WORKTREE}" >&2
    exit 1
fi

if [[ -f /workspace/Ascend/${CANN_VERSION}/cann/set_env.sh ]]; then
    cann_env=/workspace/Ascend/${CANN_VERSION}/cann/set_env.sh
elif [[ -f /workspace/Ascend/cann/set_env.sh ]]; then
    cann_env=/workspace/Ascend/cann/set_env.sh
elif [[ -f /usr/local/Ascend/cann/set_env.sh ]]; then
    cann_env=/usr/local/Ascend/cann/set_env.sh
else
    echo "CANN environment script was not found in either fallback path" >&2
    exit 1
fi

echo "Activating CANN environment from ${cann_env}"
# shellcheck source=/dev/null
source "${cann_env}"

if [[ -f /workspace/miniforge3/etc/profile.d/conda.sh ]]; then
    conda_env_script=/workspace/miniforge3/etc/profile.d/conda.sh
elif [[ -f "${HOME}/miniforge3/etc/profile.d/conda.sh" ]]; then
    conda_env_script="${HOME}/miniforge3/etc/profile.d/conda.sh"
else
    echo "Conda was not found in either fallback path" >&2
    exit 1
fi

echo "Activating Conda from ${conda_env_script}"
# shellcheck source=/dev/null
source "${conda_env_script}"
conda activate catlass-ci-py311-torch290

cd "${RDV_WORKTREE}"
case "${CATLASS_TEST_SUITE}" in
    dsl)
        export CATLASS_DSL_PREBUILT_ASCENDNPU_IR=/workspace/AscendNPU-IR
        timeout --signal=KILL "${TEST_HARD_TIMEOUT}" bash tests/run_dsl_test.sh --device 0
        ;;
    all)
        timeout --signal=KILL "${TEST_HARD_TIMEOUT}" bash tests/run_all_test.sh 3510
        ;;
    *)
        echo "suite must be dsl or all" >&2
        exit 1
        ;;
esac
