#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf -- "${fixture}"' EXIT
cd "${fixture}"
git init -q
# Every reset below is confined to this newly created disposable fixture repo.
[[ "$(git rev-parse --show-toplevel)" == "$(pwd -P)" ]]
[[ "$(pwd -P)" == "$(cd "${fixture}" && pwd -P)" ]]
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
require 'scripts/build.sh -DCATLASS_ARCH=3510 55_case'
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
require 'scripts/build.sh -DCATLASS_ARCH=3510 catlass_examples'
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

# Execute the planner against build/runtime stubs: a handwritten example needs
# its binary before pytest, and optest should compile only the runner architecture.
git reset -q --hard "$(git rev-list --max-parents=0 HEAD)"
mkdir -p scripts mock-bin examples/62_case examples/74_case
touch examples/62_case/main.cpp examples/74_case/main.cpp
cat > scripts/build.sh <<'SH'
set -eu
[[ "$1" == -DCATLASS_ARCH=3510 ]]
mkdir -p output/bin
touch "output/bin/$2"
SH
cat > mock-bin/python3 <<'SH'
#!/usr/bin/env bash
set -eu
[[ "$*" == '-m pytest -v tests/test_example.py -k 62_ or 74_' ]]
[[ -f output/bin/62_case && -f output/bin/74_case ]]
[[ "${DEVICE_ID}" == 3 ]]
SH
cat > tests/run_optest.sh <<'SH'
set -eu
[[ "${CATLASS_ARCH_LIST}" == 3510 ]]
[[ "${DEVICE_ID}" == 3 ]]
[[ "$*" == '62_case 74_case' ]]
SH
chmod +x mock-bin/python3
git add -- .
git commit -qm execution-base
RDV_BASE_SHA="$(git rev-parse HEAD)"
printf '\nchanged\n' >> examples/62_case/main.cpp
printf '\nchanged\n' >> examples/74_case/main.cpp
git add -- .
git commit -qm execution-change
RDV_HEAD_SHA="$(git rev-parse HEAD)"
PATH="${fixture}/mock-bin:${PATH}" DEVICE_ID=3 CI_DRY_RUN=0 bash "${planner}"
echo 'Eight routing scenarios and the selective build/runtime contract passed'
