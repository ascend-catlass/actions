# Publish a AtomGit release bundle

[中文](../../zh/actions/atomgit-release.md) · [English](../../en/actions/atomgit-release.md)

`atomgit-release`

## What it does

Uploads an already built and validated wheel bundle to a AtomGit Release. Existing assets are compared by content: matching assets are reused and conflicting assets fail the run.

## When to use it

Use it in the AtomGit distribution step of a stable release. It neither builds wheels nor publishes to PyPI.

## What happens

1. Check that the bundle contains eight wheels, SHA256SUMS and release-notes.md.
2. Find the Release for the selected tag, create it if needed, and upload missing assets.
3. Verify SHA-256 for existing assets and read back the Release to check expected asset visibility.

## Before you run it

- A Linux runner with Python 3 and curl. The token needs Release write permissions.
- bundle must point to a prepared directory containing wheels/, SHA256SUMS and release-notes.md. The parent release workflow first verifies that the stable tag exists.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/atomgit-release@main
  with:
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
    tag: ${{ inputs.catlass_tag }}
    version: ${{ needs.preflight.outputs.version }}
    bundle: 'release-bundle'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `token` | Yes | — | AtomGit release token from an Actions secret |
| `owner` | No | `cann` | AtomGit repository owner |
| `repo` | No | `catlass` | AtomGit repository name |
| `tag` | Yes | — | Exact release tag |
| `version` | Yes | — | Exact package version |
| `bundle` | Yes | — | Validated release bundle directory |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

No Action output fields are defined. Check the step status, logs or the external result it writes.

## Notes and common questions

- No Action output fields are defined. Use the step exit status and logs to determine success.
- A rerun reuses identical remote assets and does not overwrite conflicting files. Final verification checks asset-name visibility; it does not redownload every newly uploaded asset.

## Implementation and callers

- [.github/actions/atomgit-release/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/atomgit-release/action.yml)
- [scripts/prepare_atomgit_assets.py](https://github.com/ascend-catlass/actions/blob/main/scripts/prepare_atomgit_assets.py)
- [.github/workflows/release-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/release-dsl-wheel.yml)
