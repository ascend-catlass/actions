# Create an Ascend test container

[中文](../../zh/actions/create-ascend-container.md) · [English](../../en/actions/create-ascend-container.md)

`create-ascend-container`

## What it does

Prepares a disposable Ascend container for tests. A runner already inside a container keeps its current environment. A host runner creates a container and mounts source code plus the required driver files.

## When to use it

Use it when PR tests need a consistent image while supporting both host and container runners.

## What happens

1. Check /.dockerenv to determine whether the runner is already containerized.
2. On a host, build the selected lightweight image if absent, then mount source, weekly CANN, NPUIR and drivers. Image creation is locked and rechecked to avoid duplicate concurrent builds.
3. Return the source path and container name to downstream test steps.

## Before you run it

- A Linux Ascend test environment. Host mode requires Docker, installed NPU drivers, provisioned weekly CANN and a matching NPUIR archive. Missing images are built immediately.
- worktree must be an existing absolute host path; name must be unique.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/create-ascend-container@main
  with:
    name: catlass-test-${{ github.run_id }}-${{ github.run_attempt }}
    worktree: ${{ github.workspace }}/catlass
```

```yaml
- name: Clean up the managed container
  if: ${{ always() && steps.action.outputs.container-name != '' }}
  shell: bash
  env:
    CONTAINER_NAME: ${{ steps.action.outputs.container-name }}
  run: docker rm --force "$CONTAINER_NAME"
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `image-repository` | No | `ascend-catlass-dsl` | Container image repository (CANN_REPO) |
| `image-tag` | No | `ubuntu24-py312-weekly-v1` | Container image tag (CANN_TAG) |
| `base-image` | No | `ubuntu:24.04` | Ubuntu 24.04 base used only for missing-image builds |
| `cann-root` | No | `/opt/cann_weekly/latest/ascend-toolkit` | Weekly CANN toolkit; real version directory mounted read-only |
| `npuir-root` | No | `/opt/AscendNPU-IR/latest/AscendNPU-IR` | Prepared NPUIR tree mounted read-only |
| `name` | Yes | — | Unique container name (NAME) |
| `worktree` | Yes | — | Existing host source directory to mount |
| `container-worktree` | No | `/workspace/catlass` | Source directory inside the new container |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `container-name` | Name of the managed container; empty when already inside a container |
| `worktree` | Source path to use for tests in the selected environment |

## Notes and common questions

- Host mode uses --privileged for NPU access. Drivers, weekly CANN and NPUIR are mounted read-only; Python 3.12 and CPU PyTorch come from the lightweight image. Every test shell activates weekly CANN. Startup validates the source gitlink against the NPUIR archive and imports acl/TorchNPU before continuing.
- The production PR workflow uses the tested Ubuntu mirror. Override `base-image` with another trusted Ubuntu 24.04 image/digest as needed. Provision CANN and NPUIR first; the image build does not rebuild or install either dependency.
- Use `validate-dsl-environment.yml` to build a missing image and run the complete DSL gate on either replacement machine or both. Existing images are reused; change the image tag when intentionally changing image dependencies.
- The Action does not delete containers. The caller needs an always() cleanup step for a nonempty container-name. Container-runner mode returns an empty name and must leave the original runner alone.
- The RDV workflow also removes the current run’s `.rdv-work/pr-run-id-attempt` source and build directory. Removing a container leaves its host bind mount intact; host runners need noninteractive `sudo` to remove files created as root. Cleanup validates the path and container name and preserves other runs and NPUIR caches.

## Implementation and callers

- [.github/actions/create-ascend-container/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/create-ascend-container/action.yml)
- [.github/actions/create-ascend-container/create-ascend-container.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/create-ascend-container/create-ascend-container.sh)
- [.github/workflows/test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml)
