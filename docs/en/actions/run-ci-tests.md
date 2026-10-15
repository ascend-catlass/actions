# Run a CATLASS test stage

[中文](../../zh/actions/run-ci-tests.md) · [English](../../en/actions/run-ci-tests.md)

`run-ci-tests`

## What it does

Runs one explicit stage in a prepared test environment. DSL testing separates development build, IR, Lit and device tests. Non-DSL testing selects groups from changed paths and reverse header dependencies.

## When to use it

Use it after the workflow merges the PR, prepares the environment and selects an NPU.

## What happens

1. Choose the current container, a managed container or the legacy host environment.
2. Run the selected dsl-dev, dsl-ir, dsl-lit, dsl or all stage.
3. Write commands and results to logs; propagate a nonzero exit status to the parent workflow.

## Before you run it

- A merged CATLASS worktree with matching CANN, Python, build tools and NPU environment.
- dsl-ir and dsl-lit require an earlier dsl-dev build. Selective non-DSL testing needs the actual base-sha and head-sha.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/run-ci-tests@main
  with:
    suite: 'all'
    worktree: ${{ steps.container.outputs.worktree }}
    container: ${{ steps.container.outputs.container-name }}
    device-id: ${{ steps.prepare.outputs.device-id }}
    base-sha: ${{ steps.merge.outputs.base_sha }}
    head-sha: ${{ needs.prepare.outputs.head_sha }}
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `suite` | Yes | — | Test suite to run (dsl-dev, dsl-ir, dsl-lit, dsl or all) |
| `worktree` | Yes | — | Merged CATLASS worktree to test |
| `container` | No | `""` | Running Docker container in which to execute the tests (empty runs on the host) |
| `device-id` | No | `0` | Runtime device index selected before testing |
| `base-sha` | No | `""` | PR target commit required for selective non-DSL tests |
| `head-sha` | No | `""` | PR head commit for selective non-DSL tests |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

No Action output fields are defined. Check the step status, logs or the external result it writes.

## Notes and common questions

- suite=all enters selective non-DSL testing; it does not always run every test. Shared build dependencies trigger the full 3510 suite; unsupported 910B-only groups do not run on 950.
- The parent PR workflow decides whether documentation/image changes skip NPU work and how DSL/non-DSL changes are routed.
- No Action output fields are defined. Direct host execution activates the legacy CANN/Conda setup; containers use the image environment.

## Implementation and callers

- [.github/actions/run-ci-tests/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/action.yml)
- [.github/actions/run-ci-tests/run-ci-tests.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/run-ci-tests.sh)
- [.github/actions/run-ci-tests/run-targeted-tests.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/run-targeted-tests.sh)
- [.github/actions/run-ci-tests/run-dsl-unit-tests.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/run-dsl-unit-tests.sh)
- [.github/actions/run-ci-tests/SOURCE.md](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md)
- [.github/workflows/test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml)
