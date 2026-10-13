#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf -- "${fixture}"' EXIT
mkdir -p "${fixture}/work/python/tla_dsl" "${fixture}/cann" "${fixture}/bin"
export RDV_WORKTREE="${fixture}/work" ASCEND_HOME_PATH="${fixture}/cann"
export CALL_LOG="${fixture}/calls"
export CATLASS_DSL_PREBUILT_ASCENDNPU_IR="${fixture}/npuir"
printf ':\n' > "${ASCEND_HOME_PATH}/set_env.sh"
cat > "${RDV_WORKTREE}/python/tla_dsl/build.sh" <<'SH'
echo "dev-build:$*" >> "${CALL_LOG}"
exit "${BUILD_EXIT:-0}"
SH
cat > "${fixture}/bin/python" <<'SH'
#!/usr/bin/env bash
echo "python:$*" >> "${CALL_LOG}"
if [[ "$*" == *'pytest'* ]]; then exit "${IR_EXIT:-0}"; fi
if [[ "$*" == *'pip install'* ]]; then exit "${PIP_EXIT:-0}"; fi
SH
cat > "${fixture}/bin/cmake" <<'SH'
#!/usr/bin/env bash
echo "cmake:$*" >> "${CALL_LOG}"
exit "${LIT_EXIT:-0}"
SH
chmod +x "${fixture}/bin/"*
export PATH="${fixture}/bin:${PATH}"
runner="${repo}/.github/actions/run-ci-tests/run-dsl-unit-tests.sh"
bash "${runner}" dsl-dev
bash "${runner}" dsl-ir
bash "${runner}" dsl-lit
grep -q '^dev-build:$' "${CALL_LOG}"
grep -Fq 'python:-m pip install --index-url https://mirrors.nju.edu.cn/pypi/web/simple lit' "${CALL_LOG}"
grep -q '^python:-m pytest -q tests -p no:randomly --durations=20$' "${CALL_LOG}"
grep -q '^cmake:--build csrc/mlir/build --target check-tla-lit$' "${CALL_LOG}"
if BUILD_EXIT=5 bash "${runner}" dsl-dev; then echo 'Build failure was hidden'; exit 1; fi
if IR_EXIT=7 bash "${runner}" dsl-ir; then echo 'IR failure was hidden'; exit 1; fi
if LIT_EXIT=9 bash "${runner}" dsl-lit; then echo 'Lit failure was hidden'; exit 1; fi
if PIP_EXIT=6 bash "${runner}" dsl-dev; then echo 'Lit install failure was hidden'; exit 1; fi
if bash "${runner}" invalid; then echo 'Invalid stage was accepted'; exit 1; fi
echo 'DSL unit stage command and failure checks passed.'
