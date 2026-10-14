# Reuse local AscendNPU-IR build archives

[中文](../../zh/actions/npuir-local-archive.md) · [English](../../en/actions/npuir-local-archive.md)

`npuir-local-archive`

## What it does

Stores and reuses complete AscendNPU-IR source, build and install trees on each build host. An archive is returned only when its commit, CPU architecture and build contract match the request.

## When to use it

Use it when DSL wheel builds need to reuse a costly compiled dependency or publish a newly completed dependency tree.

## What happens

1. lookup: find the local dated archive, validate its manifest, or return a temporary build path when absent.
2. The caller builds in work_path. The Action itself does not compile.
3. publish: validate and publish the completed tree, then update latest under a local file lock without moving its date backwards.

## Before you run it

- A Linux self-hosted build host with Git, GNU command-line tools and flock. The archive root must be writable.
- Creating the default /opt/AscendNPU-IR may require passwordless sudo. publish needs a completed source_path.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/npuir-local-archive@main
  with:
    operation: 'lookup'
    source_sha: '693abf31f3d88d13d30d9578fcf6513b90c0ee33'
    target_arch: 'x86_64'
    build_contract: 'clang19-lld19-release-rtti-assert-triton-zstd-off-v1'
    baseline_date: '20261013'
    build_fingerprint: 'clang-19.1.7+lld-19.1.7'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `operation` | Yes | — | Operation to perform (lookup or publish) |
| `source_sha` | Yes | — | Exact AscendNPU-IR source commit represented by the archive |
| `target_arch` | Yes | — | Target CPU architecture, such as x86_64 or aarch64 |
| `build_contract` | Yes | — | Human-readable version of the build options and toolchain contract |
| `baseline_date` | Yes | — | Version date (YYYYMMDD), used for directory and latest ordering |
| `archive_root` | No | `/opt/AscendNPU-IR` | Shared archive root on this worker |
| `source_path` | No | `""` | Completed per-run tree to publish; required for publish |
| `source_branch` | No | `""` | Source branch recorded in the archive manifest |
| `source_ref` | No | `""` | Requested source ref recorded in the archive manifest |
| `build_fingerprint` | No | `""` | Exact installed toolchain fingerprint to record or require |
| `legacy_postfix` | No | `""` | Old runner-local date suffix eligible for migration |
| `legacy_build_fingerprint` | No | `""` | Build fingerprint required when reusing the old date-based archive |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `path` | Absolute dated archive path; on a cache miss this is only the planned path, not a completed tree. |
| `work_path` | Same-filesystem temporary path where the caller can build a missing archive |
| `archive_key` | Content-oriented archive key |
| `source_sha` | AscendNPU-IR source commit stored in the selected archive |
| `target_arch` | Target CPU architecture stored in the selected archive |
| `build_contract` | Build contract stored in the selected archive |
| `baseline_date` | Version date stored in the selected archive |
| `build_fingerprint` | Toolchain fingerprint stored in the selected archive |
| `cache_hit` | Whether lookup found an existing completed archive |
| `legacy_cache_hit` | Whether lookup migrated an old runner-local archive |

## Notes and common questions

- Each host keeps its own archives; this is not a cross-host remote cache. The layout is `/opt/AscendNPU-IR/<date>/AscendNPU-IR`.
- A date cannot be reused for a different commit, architecture or build contract. Conflicts fail rather than silently overwrite; failed builds never become latest.
- Legacy migration requires matching legacy parameters. The selected source commit must still match the dependency gitlink required by CATLASS.

## Implementation and callers

- [.github/actions/npuir-local-archive/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/npuir-local-archive/action.yml)
- [.github/actions/npuir-local-archive/manage-archive.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/npuir-local-archive/manage-archive.sh)
- [.github/workflows/build-ascendnpu-ir-20261013.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20261013.yml)
- [.github/workflows/build-ascendnpu-ir-20260720.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20260720.yml)
- [.github/workflows/build-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-dsl-wheel.yml)
- [.github/workflows/migrate-npuir-cache.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/migrate-npuir-cache.yml)
