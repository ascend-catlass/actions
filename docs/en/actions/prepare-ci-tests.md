# Prepare test dependencies and select an NPU

[中文](../../zh/actions/prepare-ci-tests.md) · [English](../../en/actions/prepare-ci-tests.md)

`prepare-ci-tests`

## What it does

Installs project Python dependencies in the selected test environment and chooses an eligible NPU with fewer running processes.

## When to use it

Run it after environment preparation and before DSL or non-DSL tests.

## What happens

1. Create a temporary filtered requirements file, omit direct Torch, Torch NPU and Lit declarations, and install the remaining dependencies with pip.
2. Run detect_npu.sh in the test environment to inspect eligible cards.
3. Select by process count and then card ID, returning device-id.

## Before you run it

- An existing CATLASS worktree, Python/pip, Bash, awk and working npu-smi.
- The image or environment must already provide matching Torch and Torch NPU. Pass container for a managed container created on a host.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/prepare-ci-tests@main
  with:
    worktree: ${{ steps.container.outputs.worktree }}
    container: ${{ steps.container.outputs.container-name }}
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `worktree` | Yes | — | Source path in the test environment |
| `container` | No | `""` | Managed Docker container; empty for a container runner |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `device-id` | NPU card ID selected by the upstream detect_npu.sh for DEVICE_ID |

## Notes and common questions

- Filtering applies to direct requirements; pip still resolves transitive dependencies. The original requirements.txt is unchanged, and the DSL dev stage may still install Lit.
- Default eligibility requires more than 1024 MB free memory and fewer than four processes. No candidate fails preparation. Selection is a snapshot, not an exclusive reservation.
- The selector comes from flash-attention-npu; its source attribution and license are kept with the Action.

## Implementation and callers

- [.github/actions/prepare-ci-tests/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/prepare-ci-tests/action.yml)
- [.github/actions/prepare-ci-tests/detect_npu.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/prepare-ci-tests/detect_npu.sh)
- [.github/actions/prepare-ci-tests/SOURCE.md](https://github.com/ascend-catlass/actions/blob/main/.github/actions/prepare-ci-tests/SOURCE.md)
- [.github/workflows/test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml)
