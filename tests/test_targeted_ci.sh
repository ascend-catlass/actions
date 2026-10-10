#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf -- "${fixture}"' EXIT
cd "${fixture}"
git init -q
# Every reset below is confined to this newly created disposable fixture repo.
[[ "$(cd "$(git rev-parse --show-toplevel)" && pwd -P)" == "$(pwd -P)" ]]
[[ "$(pwd -P)" == "$(cd "${fixture}" && pwd -P)" ]]
git config user.name ci-test
git config user.email ci-test@example.invalid
mkdir -p examples/55_case include/catlass tests/tools tests/optest/tests python/catlass_cppgen tools/tuner
touch examples/55_case/main.cpp include/catlass/shared.hpp
# Exercise the adapter/selector contract, not the upstream scanner algorithm.
cat > tests/tools/get_test_example_case_list.py <<'PY'
print("55_case")
PY
touch tests/optest/build.sh tests/optest/tests/test_55_case.py python/catlass_cppgen/example.py tests/test_example.py tools/tuner/main.cpp
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
reject 'scripts/build.sh -DCATLASS_ARCH=3510 55_case'
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
reject 'scripts/build.sh -DCATLASS_ARCH=3510 catlass_examples'
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
reject 'tests/run_all_test.sh 3510'
require 'catlass_unittest_3510'

saved_base="${RDV_BASE_SHA}"
RDV_BASE_SHA=''
if bash "${planner}"; then echo 'Missing diff must fail' >&2; exit 1; fi
RDV_BASE_SHA="${saved_base}"

change tools/tuner/main.cpp
reject 'tests/run_all_test.sh'
reject '>>> '
require '910B-only test group'

change tests/optest/tests/test_55_case.py
require 'tests/run_optest.sh 55_optest'
reject 'tests/test_example.py'
reject 'tests/run_all_test.sh'

# A shared optest change must override narrowed cases from an example change.
git reset -q --hard "${RDV_BASE_SHA}"
printf '\nchanged\n' >> examples/55_case/main.cpp
printf '\nchanged\n' >> tests/optest/build.sh
git add -- .
git commit -qm mixed
RDV_HEAD_SHA="$(git rev-parse HEAD)"
output="$(bash "${planner}")"
require 'tests/run_optest.sh '
reject 'tests/run_optest.sh 55_case'
reject 'tests/run_all_test.sh'

# No corresponding optest: avoid building a wheel that would run no cases.
git reset -q --hard "${RDV_BASE_SHA}"
mkdir -p examples/99_no_optest
touch examples/99_no_optest/main.cpp
git add -- .
git commit -qm no-optest
RDV_HEAD_SHA="$(git rev-parse HEAD)"
output="$(bash "${planner}")"
require 'tests/test_example.py -k 99_'
reject 'tests/run_optest.sh'

# Empty selector results and unrelated angle includes are valid, as in GitCode.
git reset -q --hard "${RDV_BASE_SHA}"
printf '#include <catlass/shared.hpp>\n' > include/catlass/angle.hpp
printf '\nchanged\n' >> include/catlass/shared.hpp
git add -- .
git commit -qm empty-selector
RDV_HEAD_SHA="$(git rev-parse HEAD)"
# Change the fixture scanner's result without adding a scanner change to the PR.
printf 'print("")\n' > tests/tools/get_test_example_case_list.py
output="$(bash "${planner}")"
require 'catlass_unittest_3510'
reject 'tests/run_all_test.sh'
reject 'tests/test_example.py'
reject 'tests/run_optest.sh'

# Actual selector failures must not be turned into expensive full-suite runs.
printf 'raise RuntimeError("scanner failed")\n' > tests/tools/get_test_example_case_list.py
if bash "${planner}"; then echo 'Scanner failure must fail CI' >&2; exit 1; fi

git reset -q --hard "${RDV_BASE_SHA}"
mkdir -p tests/optest/kernels/55_case
touch tests/optest/kernels/55_case/main.cpp
git add -- .
git commit -qm numbered-kernel
RDV_HEAD_SHA="$(git rev-parse HEAD)"
output="$(bash "${planner}")"
require 'tests/run_optest.sh 55_optest'
reject 'tests/test_example.py'
reject 'tests/run_all_test.sh'

change unrelated-ci-config.yml
reject '>>> '
reject 'tests/run_all_test.sh'

git reset -q --hard "${RDV_BASE_SHA}"
git rm -qr examples/55_case
git commit -qm removed-example
RDV_HEAD_SHA="$(git rev-parse HEAD)"
output="$(bash "${planner}")"
reject 'tests/run_all_test.sh'
reject '>>> '

# Execute the planner against runtime stubs: pytest owns example compilation,
# and optest should compile only the runner architecture.
git reset -q --hard "$(git rev-list --max-parents=0 HEAD)"
mkdir -p scripts mock-bin examples/62_case examples/74_case
touch examples/62_case/main.cpp examples/74_case/main.cpp
touch tests/optest/tests/test_62_case.py tests/optest/tests/test_74_case.py
cat > scripts/build.sh <<'SH'
echo 'Unexpected example prebuild' >&2
exit 1
SH
cat > mock-bin/python3 <<'SH'
#!/usr/bin/env bash
set -eu
[[ "$*" == '-m pytest -v tests/test_example.py -k 62_ or 74_' ]]
[[ ! -d output/bin ]]
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
echo 'Selective routing scenarios and the build/runtime contract passed'
