# Reset RDV labels

[中文手册](../../../docs/zh/actions/atomgit-rdv-reset.md) · [English guide](../../../docs/en/actions/atomgit-rdv-reset.md)


Removes `RDV-SUCC`, `RDV-FAIL` and `RDV-RUNNING` from a pull request.

These labels describe the outcome of one RDV run. After the PR changes, that
outcome no longer reflects the current code, so the labels are cleared and the
PR must be tested again.

## Inputs

| Input | Required | Description |
| --- | --- | --- |
| `pr-number` | yes | Pull request number in `cann/catlass` |
| `token` | yes | AtomGit token with label write permission |

## Outputs

| Output | Values |
| --- | --- |
| `result` | `removed:<labels>`, `no_rdv_label`, `pr_not_open` |

## Behaviour

- Closed or merged PRs are left alone.
- Only the three RDV result labels are touched; other labels stay.
- Every delete is verified with a follow-up GET. A delete that does not take
  effect raises instead of reporting success.
