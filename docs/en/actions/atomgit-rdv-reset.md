# Reset RDV labels

[中文](../../zh/actions/atomgit-rdv-reset.md) · [English](../../en/actions/atomgit-rdv-reset.md)

`atomgit-rdv-reset`

## What it does

Removes `RDV-SUCC`, `RDV-FAIL` and `RDV-RUNNING` from a pull request.

The labels describe the outcome of one RDV run. Once the PR changes that
outcome no longer applies, so the labels are cleared and the PR goes back to
needing a test.

## When to use it

Dispatched by the gateway when a PR has a real update and still carries any of
those labels.

## Process

1. Read the PR state and its labels.
2. Stop at once if the PR is closed or merged.
3. Delete each RDV label that is present.
4. Read the PR back and confirm removal; raise if a label is still there.

## Before you start

- GitHub-hosted Linux runner; the Action uses Python 3.12.
- An ATOMGIT_TOKEN that can write PR labels (falls back to GITCODE_TOKEN when empty).
- Only targets cann/catlass.

## Example

```yaml
- uses: ascend-catlass/actions/.github/actions/atomgit-rdv-reset@main
  with:
    pr-number: '123'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
```

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `pr-number` | Yes | — | Pull request number in cann/catlass. |
| `token` | Yes | — | AtomGit token that can write PR labels. |

## Outputs

| Output | Description |
| --- | --- |
| `result` | `removed:<labels>`, `no_rdv_label` or `pr_not_open`. |

## Notes

Only these three labels are touched. Every delete is verified with a fresh
read so a failed removal is never reported as success.
