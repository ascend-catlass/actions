# Classify an Issue

[中文](../../zh/actions/atomgit-issue-label.md) · [English](../../en/actions/atomgit-issue-label.md)

## Purpose

Community 1 combines Issue analysis and classification in one AI execution.
Classification includes every author, including committers and maintainers. The shared CATLASS AI stage receives no publishing credentials.
Candidates are the existing Issue-kind labels: documentation, feature, bug-report,
wontfix, question, enhancement, bug, kind/feature, requirement, tech-debt, invalid,
duplicate and RFC. Only names present in the live catalogue are candidates.

Publish consumes the successful AI response and provenance together, rechecks the
Issue content/state/labels and catalogue, adds exactly one label and reads it back.
Existing category labels are preserved; other labels are never replaced. Changed
content fails without writing; closed/confidential Issues are skipped. Analysis comments do not invalidate classification.

## Example

Use a checkout of this repository and the workflow's pinned shared_actions helpers.
The model stage runs between prepare and publish.

```yaml
- uses: ascend-catlass/actions/.github/actions/atomgit-issue-label@main
  with:
    operation: prepare
    issue-number: '739'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
```

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `operation` | Yes | — | prepare or publish |
| `token` | Yes | — | Issue/label read and label write credential |
| `issue-number` | No | `""` | Required for prepare; cann/catlass Issue number |
| `result-directory` | No | `_issue-label-result` | Context and publication evidence |
| `stage-result` | No | `""` | Required for publish; successful AI stage result |

## Outputs

| Output | Meaning |
| --- | --- |
| `analyze` | true only when preparation is ready |
| `result` | ready, labeled, already_classified, issue_not_open or confidential_issue |

## Operation

Public open/reopen events dispatch Community 1 once. Reply author-role filtering
never disables classification. Existing category labels are preserved; update
events are ignored. Manual dispatch recovers missed events; publish=false writes nothing. Per-Issue concurrency and publication rechecks
make redelivery idempotent. No labels are created; classification never comments,
closes Issues or triggers fixes. Lack of detail does not justify wontfix.
