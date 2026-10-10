#!/usr/bin/env bash
# Adapted from CATLASS .gitcode/scripts/pre_smoke.sh's test selection rules.
# Uses the merged repository's tests/tools/get_test_example_case_list.py.
set -euo pipefail

cd "${RDV_WORKTREE:?}"
export CATLASS_ARCH_LIST=3510
full=false
self_contained=false
unittest=false
examples_all=false
optest=false
optest_all=false
cppgen=false
cases=()
operator_cases=()
example_paths=()
failed=0
diff_file="$(mktemp)"
trap 'rm -f -- "${diff_file}"' EXIT

run_test() {
    printf '>>> '; printf '%q ' "$@"; echo
    if [[ "${CI_DRY_RUN:-0}" == 1 ]]; then return 0; fi
    if "$@"; then return 0; else failed=1; return 0; fi
}

if [[ -z "${RDV_BASE_SHA:-}" || -z "${RDV_HEAD_SHA:-}" ]] ||
   ! git -c safe.directory="${PWD}" diff --no-renames --name-only -z \
       "${RDV_BASE_SHA}...${RDV_HEAD_SHA}" > "${diff_file}"; then
    echo "Cannot select tests without a reliable PR diff" >&2
    exit 1
fi

while IFS= read -r -d '' path; do
    case "${path}" in
        docs/* | *.md | *.rst | *.png | *.jpg | *.jpeg | *.gif | *.svg | *.webp | *.bmp | *.ico) ;;
        python/tla_dsl/* | tests/dsl_battery/* | tests/run_dsl_test.sh) ;;
        include/*)
            self_contained=true
            unittest=true
            example_paths+=("${path}")
            ;;
        examples/[0-9]*_*/*)
            case_name="${path#examples/}"; case_name="${case_name%%/*}"
            if [[ -d "examples/${case_name}" ]]; then
                cases+=("${case_name}")
            else
                echo "Removed example: ${case_name}; no remaining case to run"
            fi
            ;;
        tests/unittest/* | tests/run_unittest.sh) unittest=true ;;
        tests/optest/tests/test_[0-9]*_*.py | tests/optest/kernels/[0-9]*_*/*)
            optest=true
            case_name="${path#tests/optest/}"
            case_name="${case_name#tests/test_}"
            case_name="${case_name#kernels/}"
            operator_cases+=("${case_name%%_*}_optest")
            ;;
        tests/optest/* | tests/run_optest.sh) optest=true; optest_all=true ;;
        python/catlass_cppgen/* | tests/run_cppgen.sh) cppgen=true ;;
        tests/test_example.py)
            examples_all=true
            ;;
        tests/tools/get_test_example_case_list.py)
            examples_all=true
            optest=true
            optest_all=true
            ;;
        CMakeLists.txt | cmake/* | 3rdparty/* | scripts/build.sh | tests/test_compile.sh | tests/run_all_test.sh | requirements.txt)
            echo "Shared build/test dependency changed: ${path}; full non-DSL suite required"
            full=true
            ;;
        examples/python_extension/* | tests/test_python_extension.py | tests/test_torch_lib.py | src/torch/* | tools/tuner/*)
            echo "910B-only test group: ${path}; not part of the Ascend 950 suite"
            ;;
        *)
            echo "No non-DSL test group selected for ${path} (same as GitCode pre_smoke)"
            ;;
    esac
done < "${diff_file}"

if [[ "${full}" != true && ${#example_paths[@]} -gt 0 ]]; then
    selector=tests/tools/get_test_example_case_list.py
    printf '%s\n' "${example_paths[@]}" > "${diff_file}"
    # Follow GitCode: an empty result is valid; an actual scanner error fails CI.
    selected="$(python3 "${selector}" --difflist "${diff_file}")" || exit 1
    while IFS= read -r case_name; do
        [[ -z "${case_name}" ]] && continue
        if [[ ! "${case_name}" =~ ^[0-9]+_[A-Za-z0-9_]+$ ]]; then
            echo "Invalid selector output: ${case_name}" >&2
            exit 1
        fi
        [[ -d "examples/${case_name}" ]] && cases+=("${case_name}")
    done <<< "${selected}"
fi

if [[ ${#cases[@]} -gt 0 ]]; then
    mapfile -t cases < <(printf '%s\n' "${cases[@]}" | sort -u)
fi
echo "Test selection: full=${full}, self-contained=${self_contained}, unittest=${unittest}, examples-all=${examples_all}, optest-all=${optest_all}, cppgen=${cppgen}"
echo "Affected examples: ${cases[*]:-<none>}"

if [[ "${full}" == true ]]; then
    run_test bash tests/run_all_test.sh 3510
    exit "${failed}"
fi

if [[ "${self_contained}" == true ]]; then
    run_test bash scripts/build.sh --clean -DCATLASS_ARCH=3510 --tests test_self_contained_includes
fi
if [[ "${unittest}" == true ]]; then
    run_test bash scripts/build.sh --clean -DCATLASS_ARCH=3510 --tests catlass_unittest
    run_test ./build/tests/unittest/catlass_unittest_3510
fi
if [[ "${examples_all}" == true ]]; then
    run_test python3 -m pytest -v tests/test_example.py
elif [[ ${#cases[@]} -gt 0 ]]; then
    # Numeric prefixes include handwritten variants whose names differ from directories.
    filter=""
    while IFS= read -r case_name; do
        prefix="${case_name%%_*}_"
        filter+="${filter:+ or }${prefix}"
    done < <(printf '%s\n' "${cases[@]}" | sort -u)
    run_test python3 -m pytest -v tests/test_example.py -k "${filter}"
fi
if [[ ${#cases[@]} -gt 0 ]]; then
    # Preserve upstream behavior: affected examples trigger the operator build.
    optest=true
fi
if [[ "${optest}" == true ]]; then
    if [[ "${optest_all}" == true ]]; then
        run_test bash tests/run_optest.sh
    else
        # Upstream checks this only after building the wheel. Check first so
        # examples without any operator tests do not build an unused package.
        shopt -s nullglob
        candidates=("${operator_cases[@]}" "${cases[@]}")
        operator_cases=()
        for case_name in "${candidates[@]}"; do
            matches=(tests/optest/tests/test_${case_name%%_*}_*.py)
            [[ ${#matches[@]} -gt 0 ]] && operator_cases+=("${case_name}")
        done
        if [[ ${#operator_cases[@]} -gt 0 ]]; then
            mapfile -t operator_cases < <(printf '%s\n' "${operator_cases[@]}" | sort -u)
            run_test bash tests/run_optest.sh "${operator_cases[@]}"
        else
            echo "No optest tests for affected examples; skip operator wheel build"
        fi
    fi
fi
if [[ "${cppgen}" == true ]]; then run_test bash tests/run_cppgen.sh; fi
exit "${failed}"
