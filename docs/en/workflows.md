# Workflow guide

[中文](../zh/workflows.md) · [English](../en/workflows.md)

## Four community workflows

| Entry | Trigger | Result |
| --- | --- | --- |
| `reply-gitcode-issue.yml` · Community 1 | New/reopened public Issue by a non-role author, or manual | Short source-based TRAE CN analysis |
| `reply-gitcode-ci-passed.yml` · Community 2 | Passed label added to an open PR, or manual | Deduplicated reminder for PRs by every author |
| `fix-gitcode-issue.yml` · Community 3 | Manual only | Verified small patch, fork PR and `compile` comment |
| `review-gitcode-pr.yml` · Community 4 | Manual only | Evidence-based inline questions on changed code |

Select the entry in GitHub Actions, click **Run workflow**, and choose `main`. The three model tasks reuse [trae-cn](actions/trae-cn.md), pinned official China enterprise CLI 0.209.1 and DeepSeek-V4.1-Flash.

## 1. Brief Issue analysis

The dev gateway filters the native public open/reopen event and its author's username against a small community role account list. The Action rechecks the latest community declarations, reads source and discussion, and publishes or updates one short owned reply. Committers and maintainers are skipped; this entry does not assign Issues. Manual fallback takes `issue_url`; `publish=false` generates analysis only. Changed discussion blocks stale replies.

## 2. CI-passed reminder

The gateway checks open PR state, the current event's `ci-pipeline-passed` label, and the previous label set. Missing, empty, running or unchanged labels do not start a GitHub workflow. It does not query CI. Configure GitCode label-update delivery correctly, or use manual `pr_number` recovery when an event has no labels. Every PR author is eligible.

The Action's current-state query is a final publication guard. It scans all ordinary comment pages and posts the review/SIG/Ascend 950 reminder once. Runs for the same PR are serialized.

## 3. Quick simple-Issue fix

Manual inputs: `issue_number` and `validation_command`. This manual task is independent of brief Issue analysis: it needs no prior run or reply, has no author-role restriction, and neither task triggers the other. The workflow pins upstream master and the Issue discussion. TRAE CN reads the source and returns a structured simple/not-simple decision plus a minimal unified patch. Complex or unclear problems end as `needs-human` without a PR.

A separate step checks paths, applies a patch of at most ten files and runs the maintainer-selected command without publishing credentials. Automation configuration, symlinks and submodules cannot be changed by a simple fix. Failed validation stops publication. The runner is disposable Linux without an NPU; include dependency setup and meaningful tests in the command. Device-dependent problems need human handling.

After validation and a fresh discussion check, the publisher pushes a `codex/issue-*` branch to its existing personal CATLASS fork and opens an upstream master PR. It reads the PR back and posts one exact `compile` comment. Retries reuse the owned PR and command. The GitCode account needs fork push/PR/comment permissions and must be on dev's compile allowlist.

## 4. Inline PR review

Manual input: `pr_number`. The workflow pins head and base, then provides source and diff to TRAE CN. At most ten findings are accepted, each on an added/modified line in that pinned diff. No findings means no comments. Head/base changes block publication. Owned matching findings are deduplicated by source revision and content.

Publication uses GitCode's [inline comment endpoint](https://docs.gitcode.com/en/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-comments/), followed by body, author, path and head read-back. It does not approve or merge PRs. Model and publication evidence is retained for seven days.

## Tests, builds and releases

| Workflow | Purpose / schedule (Asia/Shanghai) |
| --- | --- |
| `test-gitcode-pr.yml` | Manual or allowlisted compile/rdvcompile; selective Ascend 950 tests and RDV status |
| `nightly-dsl-wheel.yml` | Daily 01:00: dual-architecture development wheels and GitHub package index |
| `release-dsl-wheel.yml` | Manual stable-tag validation, wheel build, PyPI and GitCode release |
| `build-dsl-wheel.yml` | Shared build, called by nightly/release or manually |
| `build-ascendnpu-ir-20261013.yml` | Current NPUIR preparation/archive baseline |
| `build-ascendnpu-ir-20260720.yml` | Legacy NPUIR preparation retained for diagnosis |
| `install-cann-weekly.yml` | Daily 02:00: install the same official build on both CPU architectures |
| `sync-gitcode.yml` | Daily 02:00: mirror GitCode master and tags to GitHub |

See [build and runner operations](operations.md) and individual [Action guides](index.md). Schedules may queue. Production jobs execute from main; the documentation PR check only tests and builds the site.

## Credentials and rollout

| Configuration | Consumer |
| --- | --- |
| `GITCODE_TOKEN` | Action context, PR/Issue publication, fork pushes and GitCode releases |
| `TRAE_CN_PAT` | Official TRAE CN enterprise login in the three model workflows |
| `TRAE_CN_HOST` | Optional enterprise API host variable |
| `WEBHOOK_PASSWORD` | dev inbound authentication |
| `GITHUB_ACTIONS_TOKEN` | dev dispatch to actions workflows |
| `CATLASS_DEPLOY_KEY` | GitHub mirror writes |
| PyPI Trusted Publisher | Stable release publishing in the pypi environment |

Publishing tokens are not passed into model execution. dev does not need a GitCode token. Subscribe the GitCode webhook to Issue, Pull Request and Note events, and keep the small gateway role list synchronized with community declarations. Submit features through PRs; merge actions first, then merge and deploy dev.
