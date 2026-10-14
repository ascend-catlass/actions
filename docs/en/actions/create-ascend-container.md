# Create an Ascend test container

[中文](../../zh/actions/create-ascend-container.md) · [English](../../en/actions/create-ascend-container.md)

`create-ascend-container`

## What it does

Prepares a disposable Ascend container for tests. A runner already inside a container keeps its current environment. A host runner creates a container and mounts source code plus the required driver files.

## When to use it

Use it when PR tests need a consistent image while supporting both host and container runners.

## What happens

1. Check /.dockerenv to determine whether the runner is already containerized.
2. On a host, create a container using the selected image, unique name and source mount.
3. Return the source path and container name to downstream test steps.

## Before you run it

- A Linux Ascend test environment. Host mode requires Docker, an available image and installed NPU drivers.
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
| `image-tag` | No | `9.2.0-beta.2-950-ubuntu22.04-py3.12` | Container image tag (CANN_TAG) |
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

- Host mode uses --privileged for NPU access. Driver mounts are read-only; CANN, Conda and other runtime dependencies come from the image.
- The Action does not delete containers. The caller needs an always() cleanup step for a nonempty container-name. Container-runner mode returns an empty name and must leave the original runner alone.

## Implementation and callers

- [.github/actions/create-ascend-container/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/create-ascend-container/action.yml)
- [.github/actions/create-ascend-container/create-ascend-container.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/create-ascend-container/create-ascend-container.sh)
- [.github/workflows/test-gitcode-pr-cann-9-2-beta-2.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr-cann-9-2-beta-2.yml)
- [.github/workflows/test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml)
