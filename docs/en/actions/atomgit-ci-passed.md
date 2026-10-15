# Send a review reminder after CI passes

[中文](../../zh/actions/atomgit-ci-passed.md) · [English](../../en/actions/atomgit-ci-passed.md)

`atomgit-ci-passed`

## What it does

Checks that a CATLASS PR is still open and carries ci-pipeline-passed, then reminds the contributor to contact a committer for review. An identical existing reminder prevents a duplicate post.

## When to use it

Use it for CI-passed label reminders or a maintainer-triggered reminder.

## What happens

1. Read the current PR state and labels from AtomGit.
2. Scan every page of ordinary PR comments for the exact reminder.
3. Post only when the PR is eligible and the reminder is absent; return the outcome.

## Before you run it

- A GitHub-hosted Linux runner; the Action sets up Python 3.12.
- ATOMGIT_TOKEN (falling back to the existing GITCODE_TOKEN) with PR read and comment write permissions. The implementation currently targets cann/catlass only.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/atomgit-ci-passed@main
  with:
    pr-number: '123'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `pr-number` | Yes | — | Pull request number in cann/catlass |
| `token` | Yes | — | AtomGit token with PR read and comment write permissions |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `result` | `commented`: posted; `already_reminded`: identical reminder exists; `pr_not_open`: PR is closed; `label_not_present`: passed label is absent. |

## Notes and common questions

- The reminder covers code review, SIG discussion for larger features, and asking a committer to post rdvcompile for the Ascend 950 pipeline.
- reply-atomgit-ci-passed.yml serializes runs per PR. Other callers should also serialize per PR to avoid simultaneous checks followed by duplicate writes.

## Implementation and callers

- [.github/actions/atomgit-ci-passed/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/atomgit-ci-passed/action.yml)
- [scripts/atomgit_ci_passed.py](https://github.com/ascend-catlass/actions/blob/main/scripts/atomgit_ci_passed.py)
- [.github/workflows/reply-atomgit-ci-passed.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-ci-passed.yml)
