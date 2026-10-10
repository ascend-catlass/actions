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
cppgen=false
cases=()
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
    echo "No reliable PR diff; falling back to the full non-DSL suite"
    full=true
fi

while IFS= read -r -d '' path; do
    case "${path}" in
        docs/* | *.md | *.rst | *.png | *.jpg | *.jpeg | *.gif | *.svg | *.webp | *.bmp | *.ico) ;;
        python/tla_dsl/* | tests/dsl_battery/* | tests/run_dsl_test.sh) ;;
        include/*)
            self_contained=true
            unittest=true
            example_paths+=("${path}")
            # The upstream scanner cannot resolve removed headers or non-.hpp files.
            if [[ ! -f "${path}" || "${path}" != *.hpp ]]; then full=true; fi
            ;;
        examples/[0-9]*_*/*)
            case_name="${path#examples/}"; case_name="${case_name%%/*}"
            if [[ ! "${case_name}" =~ ^[0-9]+_[A-Za-z0-9_]+$ || ! -d "examples/${case_name}" ]]; then
                full=true
            else
                cases+=("${case_name}")
            fi
            ;;
        tests/unittest/*) unittest=true ;;
        tests/optest/*) optest=true ;;
        python/catlass_cppgen/* | tests/run_cppgen.sh) cppgen=true ;;
        tests/test_example.py)
            examples_all=true
            ;;
        *)
            echo "Unmapped change: ${path}; falling back to the full non-DSL suite"
            full=true
            ;;
    esac
done < "${diff_file}"

if [[ "${full}" != true && ${#example_paths[@]} -gt 0 ]]; then
    selector=tests/tools/get_test_example_case_list.py
    # The upstream include graph recognizes quoted includes, not angle brackets.
    # Broad fallback for unsupported graph syntax avoids silently omitting cases.
    if [[ ! -f "${selector}" ]] ||
       grep -rEq '^[[:space:]]*#[[:space:]]*include[[:space:]]*<(catlass|tla)/' include examples; then
        full=true
    else
        printf '%s\n' "${example_paths[@]}" > "${diff_file}"
        if selected="$(python3 "${selector}" --difflist "${diff_file}")" && [[ -n "${selected}" ]]; then
            while IFS= read -r case_name; do
                if [[ "${case_name}" =~ ^[0-9]+_[A-Za-z0-9_]+$ ]]; then
                    cases+=("${case_name}")
                else
                    full=true
                fi
            done <<< "${selected}"
        else
            echo "Header dependencies could not be resolved; falling back to full tests"
            full=true
        fi
    fi
fi

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
    echo "Affected examples: ${cases[*]}"
    run_test python3 -m pytest -v tests/test_example.py -k "${filter}"
fi
if [[ ${#cases[@]} -gt 0 ]]; then
    # Preserve upstream behavior: affected examples trigger the operator build.
    optest=true
fi
if [[ "${optest}" == true ]]; then
    if [[ ${#cases[@]} -gt 0 ]]; then
        run_test bash tests/run_optest.sh "${cases[@]}"
    else
        run_test bash tests/run_optest.sh
    fi
fi
if [[ "${cppgen}" == true ]]; then run_test bash tests/run_cppgen.sh; fi
exit "${failed}"
