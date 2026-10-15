# Report RDV test status on a PR

[中文](../../zh/actions/rdv-status.md) · [English](../../en/actions/rdv-status.md)

`rdv-status`

## What it does

Reports test start and completion on an AtomGit PR by maintaining RDV-RUNNING, RDV-SUCC and RDV-FAIL labels and posting comments with workflow links. Failures may include a diagnosis in the same result comment.

## When to use it

Call start when PR testing begins and finish from the reporting step after testing.

## What happens

1. Remove existing RDV status labels while leaving other labels alone.
2. start adds RDV-RUNNING and posts a start comment.
3. finish adds RDV-SUCC for success or RDV-FAIL otherwise, then posts a result comment.

## Before you run it

- A Linux runner with Bash and Python 3. The token needs PR label read/write and comment write permissions.
- The API target is currently fixed to cann/catlass. Provide a workflow result URL.

## Example

This is a steps excerpt, not a complete workflow. Prepare the source directory, prior step outputs or release bundle referenced below, and replace numbers and versions for your task.

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/rdv-status@main
  with:
    phase: 'start'
    pr-number: '123'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
    result-url: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `phase` | Yes | — | Status transition to perform (start or finish) |
| `pr-number` | Yes | — | Pull request number in cann/catlass |
| `token` | Yes | — | AtomGit personal access token |
| `result` | No | — | Job result used by the finish phase |
| `result-url` | Yes | — | CI result URL published in the status comment |
| `comment-id` | No | — | Reserved input; the current finish script does not use it or edit this comment. |
| `failure-analysis-file` | No | `""` | Optional UTF-8 Markdown file, appended only for finish result=failure; maximum 8 KiB. |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `comment-id` | AtomGit comment ID created by the start phase |

## Notes and common questions

- The current finish implementation posts a new result comment rather than editing the start comment. comment-id remains an input but is not used by the script.
- Only result=success counts as success in finish. Failure, cancellation, skipped or empty results produce RDV-FAIL. start returns the new comment ID.
- After TestPR fails, a separate GitHub-hosted job uses TRAE CN / DeepSeek-V4.1-Flash to analyze this attempt's logs and supplies the diagnosis through this input. Unavailable analysis adds a note while preserving failure reporting and the original link.
- Success and cancellation keep their original comments. Missing, empty or oversized files are ignored. This Action consumes the diagnosis and does not call a model itself.
- It does not send the CI-passed code-review reminder; atomgit-ci-passed handles that flow.

## Implementation and callers

- [.github/actions/rdv-status/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/rdv-status/action.yml)
- [.github/actions/rdv-status/rdv-status.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/rdv-status/rdv-status.sh)
- [.github/workflows/test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml)

The public PR status Action publishes the final body directly and verifies the new comment with bounded read-after-write retries. Read failures do not repeat comment creation.
