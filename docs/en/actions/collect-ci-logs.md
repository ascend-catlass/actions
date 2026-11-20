# Collect failed CI logs

[中文](../../zh/actions/collect-ci-logs.md) · [English](../../en/actions/collect-ci-logs.md)

`collect-ci-logs`

## What it does

Reads the failed job logs of one GitHub run attempt, locates the failure, keeps 200 lines around it and publishes a redacted Markdown comment attachment. No AI analysis is involved.

## When to use it

The pipeline stops at the first failure, so the surrounding log already identifies the problem without model inference. The caller decides how to publish the attachment.

## Process

1. Official `actions/github-script` lists the failed jobs of that attempt (up to four) and downloads each log.
2. A small script matches failure markers from the end of the log (`##[error]`, `[detect_npu][ERROR]`, `FAILED`, `Traceback`, `fatal:`, a non-zero exit code) and treats the last one as the failure point.
3. It keeps the requested number of lines around that point, strips ANSI colour and timestamps, and redacts tokens, passwords, `Authorization` headers and credentials embedded in URLs.
4. It writes `analysis.md`; when logs are missing, empty or contain no marker it writes an unavailable note and still returns a usable attachment.

## Before you run it

- A GitHub-hosted runner. `github-token` needs Actions read permission on the caller repository.
- It only reads logs; no PR source is checked out or executed.

## Example

The following are workflow steps, not a complete workflow. Replace the run ID and attempt for the target task.

```yaml
- id: excerpt
  uses: ascend-catlass/actions/.github/actions/collect-ci-logs@main
  with:
    github-token: ${{ github.token }}
    run-id: ${{ github.run_id }}
    run-attempt: ${{ github.run_attempt }}
```

```yaml
- name: Save the comment attachment
  if: ${{ always() && steps.excerpt.outputs.excerpt-file != '' }}
  uses: actions/upload-artifact@v4
  with:
    name: rdv-failure-logs-${{ github.run_attempt }}
    path: ${{ steps.excerpt.outputs.excerpt-file }}
    retention-days: 7
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `github-token` | Yes | — | GitHub token with Actions read permission on the caller repository |
| `run-id` | Yes | — | Workflow run to inspect |
| `run-attempt` | No | `1` | Attempt number to inspect |
| `context-lines` | No | `200` | Log lines kept around the failure marker, 1–2000 |

Required follows action.yml. Some optional fields become necessary for a particular operation; see the process and notes.

## Outputs

| Output | Meaning |
| --- | --- |
| `excerpt-file` | Path to the Markdown excerpt, or a note when unavailable |
| `status` | `collected` or `unavailable` |

## Notes and common questions

- One excerpt per failed job, listed in order. When no marker exists the step fails and the render step falls back to the unavailable note.
- The attachment is capped at 60000 bytes; larger excerpts are truncated with a notice, and the full log link is always appended.
- No model is called and no TRAE CN credential is needed.

## Implementation and callers

- [.github/actions/collect-ci-logs/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/collect-ci-logs/action.yml)
- [.github/actions/collect-ci-logs/excerpt.cjs](https://github.com/ascend-catlass/actions/blob/main/.github/actions/collect-ci-logs/excerpt.cjs)
- [.github/workflows/test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml)
