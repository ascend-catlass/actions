# Selective non-DSL tests

`run-targeted-tests.sh` adapts the selection rules in CATLASS
`.gitcode/scripts/pre_smoke.sh` (GitCode master blob
`8a847fef2cfc20f5d062d9d0f7475d6693cca3cb`, inspected 2026-10-09).
It invokes the merged CATLASS repository's existing
`tests/tools/get_test_example_case_list.py` for reverse header dependencies.
The upstream files use the CANN Open Software License Agreement Version 2.0.

The adapter uses the verified PR base/head diff instead of OBS files,
forces architecture 3510, and keeps the existing container and selected device.
It does not inherit the 910B Python extension, torch library, tuner, coverage,
or DSL IR/lit jobs. DSL battery routing remains in the workflow.

Example changes select numbered cases; numeric prefixes conservatively include
handwritten variants. The pytest fixture builds only selected targets, so the
adapter omits the preceding all-example build in selective mode. Header changes
also run self-contained includes and the 3510 unittest. Operator-only changes
run optest, cppgen-only changes run cppgen, and test_example.py changes run all
example tests. Affected examples also trigger optest, as in upstream.

Missing diff/scanner, unresolved or deleted headers, angle-bracket project
includes, deleted example directories, and unknown paths fall back to
`tests/run_all_test.sh 3510`. Rename detection is disabled to include both old
and new paths. Build/requirements/shared CI changes therefore retain full tests.
Each command is logged, independent failures accumulate, and CI_DRY_RUN=1
prints commands without building or running tests.

The current upstream `run_optest.sh` exits after building the operator wheel.
Its selected case arguments affect runtime tests only if upstream enables them.
This adapter preserves that behavior: it reduces which changes trigger optest
and limits its architecture, but does not prune individual operators from the
monolithic build or claim operator runtime coverage.
