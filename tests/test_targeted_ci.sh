#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf -- "${fixture}"' EXIT
cd "${fixture}"
git init -q
git config user.name ci-test
git config user.email ci-test@example.invalid
mkdir -p examples/55_case include/catlass tests/tools tests/optest python/catlass_cppgen
touch examples/55_case/main.cpp include/catlass/shared.hpp
# Exercise the adapter/selector contract, not the upstream scanner algorithm.
cat > tests/tools/get_test_example_case_list.py <<'PY'
print("55_case")
PY
touch tests/optest/build.sh python/catlass_cppgen/example.py tests/test_example.py
git add -- .
git commit -qm base
export RDV_BASE_SHA
RDV_BASE_SHA="$(git rev-parse HEAD)"
export RDV_WORKTREE="${fixture}" CI_DRY_RUN=1
planner="${repo}/.github/actions/run-ci-tests/run-targeted-tests.sh"

change() {
    git reset -q --hard "${RDV_BASE_SHA}"
    printf '\nchanged\n' >> "$1"
    git add -- "$1"
    git commit -qm change
    export RDV_HEAD_SHA
    RDV_HEAD_SHA="$(git rev-parse HEAD)"
    output="$(bash "${planner}")"
}
require() { [[ "${output}" == *"$1"* ]] || { echo "Missing command: $1" >&2; exit 1; }; }
reject() { [[ "${output}" != *"$1"* ]] || { echo "Unexpected command: $1" >&2; exit 1; }; }

change examples/55_case/main.cpp
require 'tests/test_example.py -k 55_'
require 'tests/run_optest.sh 55_case'
reject 'tests/run_all_test.sh'
reject 'catlass_examples'
reject 'run_cppgen'

change include/catlass/shared.hpp
require 'test_self_contained_includes'
require 'catlass_unittest_3510'
require 'tests/test_example.py -k 55_'
reject 'catlass_unittest_2201'

change tests/optest/build.sh
require 'tests/run_optest.sh'
reject 'tests/test_example.py'

change python/catlass_cppgen/example.py
require 'tests/run_cppgen.sh'
reject 'tests/run_optest.sh'

change tests/test_example.py
require 'pytest -v tests/test_example.py'
reject ' -k '
reject 'run_optest'

change requirements.txt
require 'tests/run_all_test.sh 3510'

git reset -q --hard "${RDV_BASE_SHA}"
git rm -q include/catlass/shared.hpp
git commit -qm deletion
RDV_HEAD_SHA="$(git rev-parse HEAD)"
output="$(bash "${planner}")"
require 'tests/run_all_test.sh 3510'

RDV_BASE_SHA=''
output="$(bash "${planner}")"
require 'tests/run_all_test.sh 3510'
echo 'Eight targeted CI routing scenarios passed'
