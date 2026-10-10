# Selective non-DSL tests

`run-targeted-tests.sh` adapts CATLASS `.gitcode/scripts/pre_smoke.sh` for
Ascend 950. It uses the merged repository's unchanged
`tests/tools/get_test_example_case_list.py` for reverse header dependencies.
The upstream files use the CANN Open Software License Agreement Version 2.0.

The adapter uses a verified PR base/head diff instead of OBS files, keeps the
container and selected device, and sets `CATLASS_ARCH_LIST=3510` for optest.
DSL routing remains in the workflow. It does not run the 910B-only Python
extension, torch library or tuner groups; tuner changes explicitly skip testing.
GitCode files are not modified.

## Selection

- Header changes run self-contained includes, the 3510 unittest, and examples
  returned by the upstream selector. An empty example list is valid. Removed
  headers, non-.hpp headers and angle includes do not trigger extra full tests.
- Numbered example changes run their example tests and corresponding optest
  cases. Numeric prefixes include handwritten variants with different names.
  Example pytest owns compilation; there is no redundant all-example prebuild.
  Removed example directories have no remaining example case to execute.
- Numbered optest test or kernel changes select that numeric prefix. Shared
  optest changes run the complete optest group, even in a PR also changing a
  numbered example. They do not run unrelated example, unittest or cppgen groups.
- Unittest changes run unittest; cppgen changes run cppgen; test_example.py
  changes run the example group; scanner changes run example and optest groups.
- Root requirements, root/shared CMake files, third-party dependencies, the
  shared build script and full-suite scripts explicitly require the full 3510
  non-DSL suite. The changed path and reason are logged.
- Other paths select no non-DSL test group, matching GitCode pre_smoke. They do
  not automatically cause a full-suite fallback.

The adapter checks for corresponding optest files before invoking the upstream
runner, avoiding a wheel build for examples that have no operator tests.
The upstream runner still builds the complete operator wheel for architecture
3510 before running the selected files. This change does not prune kernels out
of that wheel or claim that its build is incremental.

Missing/invalid diffs and scanner failures fail selection instead of silently
running a full suite. Rename detection is disabled to include old and new paths.
Each plan and command is logged; independent test failures accumulate.
`CI_DRY_RUN=1` prints commands without building or running tests.

PR classification runs on a GitHub-hosted runner. Documentation-only PRs return
success without scheduling Ascend 950. Environment preparation and DSL/non-DSL
test execution run on Ascend 950.
