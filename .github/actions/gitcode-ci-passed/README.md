# GitCode CI-passed reminder

[中文手册](../../../docs/zh/actions/gitcode-ci-passed.md) · [English guide](../../../docs/en/actions/gitcode-ci-passed.md)

Called by `reply-gitcode-ci-passed.yml`, which the dev webhook gateway dispatches
on CATLASS PR label events. The gateway needs only `GITHUB_ACTIONS_TOKEN`;
`GITCODE_TOKEN` stays in this repository's Actions secrets.

The action reads the current `cann/catlass` PR and requires an open state and
the `ci-pipeline-passed` label. It scans all pages of ordinary PR comments and
posts the existing Chinese review/SIG/Ascend 950 reminder only if absent.
The workflow serializes runs for the same PR without cancelling an active write.
Callers using this action in other workflows should also serialize by PR.

```yaml
- uses: ascend-catlass/actions/.github/actions/gitcode-ci-passed@main
  with:
    pr-number: '123'
    token: ${{ secrets.GITCODE_TOKEN }}
```

Output `result`: `commented`, `already_reminded`, `pr_not_open`, or
`label_not_present`. Invalid responses and API errors fail the run. The token
requires PR read and comment write permissions. No PR code is checked out.
