# Read and validate PR metadata

[中文](../../zh/actions/gitcode-pr-metadata.md) · [English](../../en/actions/gitcode-pr-metadata.md)

`gitcode-pr-metadata`

## What it does

Reads the PR target branch, source branch and full commit SHA and verifies that the PR remains open. Downstream builds can use an explicit source revision.

## When to use it

Use it at the start of PR testing to obtain the branches and commit required for merging and testing.

## What happens

1. Validate the positive PR number and owner/repo repository format.
2. Read the PR through gitcode-api.
3. Check open state, branch names and the 40-character head SHA, then return metadata.

## Before you run it

- A Linux runner with Python 3, jq, Git and a token allowed to read PRs.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/gitcode-pr-metadata@main
  with:
    token: ${{ secrets.GITCODE_TOKEN }}
    pr-number: '123'
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `token` | Yes | — | GitCode token from an Actions secret |
| `pr-number` | Yes | — | Positive pull request number |
| `repository` | No | `cann/catlass` | GitCode owner/repository |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `base_ref` | Target branch |
| `head_ref` | Source branch |
| `head_sha` | Full source commit SHA |

## Notes and common questions

- This Action does not clone or merge source. The PR workflow later fetches the PR and checks that the fetched head SHA matches this output.
- A closed PR, invalid branch name or malformed SHA fails the step.

## Implementation and callers

- [.github/actions/gitcode-pr-metadata/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/gitcode-pr-metadata/action.yml)
- [.github/workflows/test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml)
