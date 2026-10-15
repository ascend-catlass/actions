# AtomGit CI-passed reminder

[中文手册](../../../docs/zh/actions/atomgit-ci-passed.md) · [English guide](../../../docs/en/actions/atomgit-ci-passed.md)

Called by `reply-atomgit-ci-passed.yml` for a manually supplied PR number.
The workflow prefers `ATOMGIT_TOKEN` and falls back to the existing `GITCODE_TOKEN` when empty. Credentials stay in Actions secrets.

The action reads the current `cann/catlass` PR and requires an open state and
the `ci-pipeline-passed` label. It scans all pages of ordinary PR comments and
posts the existing Chinese review/SIG/Ascend 950 reminder only if absent.
The workflow serializes runs for the same PR without cancelling an active write.
Callers using this action in other workflows should also serialize by PR.

```yaml
- uses: ascend-catlass/actions/.github/actions/atomgit-ci-passed@main
  with:
    pr-number: '123'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
```

Output `result`: `commented`, `already_reminded`, `pr_not_open`, or
`label_not_present`. Invalid responses and API errors fail the run. The token
requires PR read and comment write permissions. No PR code is checked out.
