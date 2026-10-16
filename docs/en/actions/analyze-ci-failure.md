# Analyze CI failure

[中文](../../zh/actions/analyze-ci-failure.md) · [English](../../en/actions/analyze-ci-failure.md)

## What it does

Takes a GitHub run ID and attempt in the caller repository, returning cause, log evidence and a next step. It has no CATLASS, PR-number or RDV dependency and can be reused by other CI workflows.

## What happens

Official actions/github-script handles authentication, pagination and log downloads. A small local script only bounds/redacts evidence, prepares the prompt and formats comment content. The shared [catlass-ai](catlass-ai.md) policy composes public CLI setup and execution; this caller has no separate host or model setting. Evidence covers at most four failed jobs. Analysis runs read-only in a separate temporary Git directory without executing tested code.

## Prerequisites

Linux x64 hosted runner with Git, Node and Bash; job permissions `contents: read` and `actions: read`; a TRAE CN enterprise PAT. No AtomGit or publishing credentials are needed. The Action creates its own workspace and needs no business-source checkout.

## Example

```yaml
- id: diagnosis
  uses: ascend-catlass/actions/.github/actions/analyze-ci-failure@main
  with:
    github-token: ${{ github.token }}
    trae-pat: ${{ secrets.TRAE_CN_PAT }}
    run-id: ${{ github.run_id }}
    run-attempt: ${{ github.run_attempt }}
```

Pass `steps.diagnosis.outputs.analysis-file` to an artifact or publishing Action. TestPR feeds it to rdv-status; the analysis component never posts comments itself.

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `github-token` | Yes | — | Actions-read token for the caller repository. |
| `trae-pat` | Yes | — | TRAE CN enterprise PAT. |
| `run-id` | Yes | — | Workflow run in the caller repository. |
| `run-attempt` | No | `1` | Exact retry attempt. |

## Outputs

| Output | Meaning |
| --- | --- |
| `analysis-file` | Markdown result path, or an unavailable-analysis note. |
| `status` | analyzed or unavailable. |

## Result handoff

Comment assembly accepts only the TRAE result-directory, validates execution status, and reads the response and requested_model together. It has no separate model or response-path argument. An unspecified model omits attribution. Analysis failure preserves the original RDV failure report.

## Failure handling

Missing failed jobs, unavailable logs or failed model execution produce unavailable output. Callers still need a fallback for whole-Action timeout or initialization failure; TestPR uses an independent report job. The model budget is five minutes; callers choose job timeout and artifact retention.
