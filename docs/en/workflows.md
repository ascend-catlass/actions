# How workflows connect the Actions

[中文](../zh/workflows.md) · [English](../en/workflows.md)

An Action performs a reusable step. A workflow connects steps into a complete process. This guide covers the existing business workflows; CANN installation and mirroring call scripts directly rather than additional custom Actions.

## Workflow directory

| Workflow | What it does | When it runs |
| --- | --- | --- |
| [test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml) | Merge and test a GitCode PR, then report RDV status | Manual; the dev webhook also dispatches for allowed accounts posting `compile` or `rdvcompile` |
| [reply-gitcode-ci-passed.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-ci-passed.yml) | Post a review reminder after CI passes | Manual; the dev webhook also dispatches on passed-label events |
| [reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml) | Assign an Issue according to its author's roles, or analyze and reply | Manual; `publish` defaults to enabled |
| [build-ascendnpu-ir-20261013.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20261013.yml) | Prepare NPUIR archives using the current date baseline | Manual or called by another workflow |
| [build-ascendnpu-ir-20260720.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20260720.yml) | Retain the earlier NPUIR baseline for debugging historical problems | Manual or called by another workflow |
| [build-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-dsl-wheel.yml) | Build and save x86_64 and aarch64 DSL wheels | Manual or called by nightly/release workflows |
| [nightly-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/nightly-dsl-wheel.yml) | Build a development version and publish to the GitHub Release-backed package index | Daily at 01:00 Asia/Shanghai, or manual |
| [release-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/release-dsl-wheel.yml) | Validate a stable tag, build and publish to PyPI and GitCode Release | Manual |
| [install-cann-weekly.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/install-cann-weekly.yml) | Install the same CANN weekly build on two CPU architectures | Daily at 02:00 Asia/Shanghai, or manual |
| [sync-gitcode.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/sync-gitcode.yml) | Mirror GitCode `master` and tags to GitHub | Daily at 02:00 Asia/Shanghai, or manual |

Cron expressions use UTC; the table converts them to Asia/Shanghai. Scheduled jobs may start later because of queuing. Execution jobs in this repository require the `main` branch; selecting another branch does not execute them.

## PR testing

1. [gitcode-pr-metadata](actions/gitcode-pr-metadata.md) reads PR branches and the head commit.
2. [rdv-status](actions/rdv-status.md) reports that testing has started.
3. A GitHub-hosted runner fetches the target branch and PR and classifies changed paths. Documentation/image-only changes finish here without scheduling Ascend 950 work.
4. Code changes go to the self-hosted `ascend950` runner for merging. A fetched PR head mismatch or merge conflict fails the run.
5. [create-ascend-container](actions/create-ascend-container.md) prepares the environment; [prepare-ci-tests](actions/prepare-ci-tests.md) installs filtered requirements and selects a device.
6. [run-ci-tests](actions/run-ci-tests.md) executes the required stages. DSL work uses a dev build, IR/Lit tests and device tests. Non-DSL work selects tests from changed paths and reverse header dependencies. Changes in both categories run both.
7. A reporting job writes the RDV result. An `always()` step cleans up managed containers.

Shared preparation, reuse of the DSL dev build, change-based test selection and automatic PR result links remove repeated manual steps. See the [selection rules](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md) for the actual test coverage.

## CI-passed review reminders

This flow is separate from RDV testing. A `ci-pipeline-passed` label event reaches dev, which dispatches the workflow. [gitcode-ci-passed](actions/gitcode-ci-passed.md) rechecks the current PR, scans all comment pages and posts a review reminder if eligible. Runs for the same PR are serialized.

dev needs only a GitHub dispatch credential for this operation. GitCode query and comment credentials stay in this repository's Actions secrets.

## Issue assignment and analysis

1. Read the author's platform account and query maintainers/committers with [community-repo-roles](actions/community-repo-roles.md).
2. A declared role-member author skips model analysis. [gitcode-issue](actions/gitcode-issue.md) posts `/assign @author-login`; repeated runs reuse an identical assignment comment owned by the current account.
3. For other eligible Issues, prepare source and discussion context and analyze read-only through [trae-cn](actions/trae-cn.md).
4. Recheck the Issue, discussion and author eligibility before publishing. A stale answer is blocked; an eligible answer creates or updates the current account's automation comment and reads it back.

The workflow selects `DeepSeek-V4.1-Flash` and signs model replies accordingly. `publish=false` disables both reply and assignment-comment publication. The entry point is currently manual; it does not subscribe to every new Issue.

## Dependency archives and wheel distribution

Each `publish` host keeps local dated NPUIR archives. [npuir-local-archive](actions/npuir-local-archive.md) verifies commit, architecture and build contract. A matching archive is reused; a missing one is compiled by the workflow. `latest` advances only to a newer date, while wheel builds still select the exact dependency required by the CATLASS gitlink.

Wheel workflows build on x86_64 and aarch64 hosts. Nightly publishes development versions to the GitHub package index. Release checks an existing GitCode stable tag before publishing to PyPI and GitCode. GitCode distribution uses [gitcode-release](actions/gitcode-release.md), reusing identical assets. `artifact_run_id` can select validated assets from an earlier release run to avoid rebuilding.

## Environment installation and mirroring

CANN weekly first pins one official build and then installs Toolkit and chip-matched ops on X64 and ARM64 `bz` hosts. Installations live under `/opt/cann_weekly/YYYYMMDD`. Completed dates are skipped and `latest` points to a completed installation. Driver and firmware updates are outside this workflow; logs are retained for 30 days.

Mirroring fetches GitCode `cann/catlass` `master` and tags, then force-updates the corresponding branch and tags in GitHub `ascend-catlass/catlass`, including pruning tags that no longer exist. Treat the destination as a mirror.

## Credentials used by the workflows

| Credential or setting | Used for |
| --- | --- |
| `GITCODE_TOKEN` | PR metadata, comments and labels; Issue reads/publication; GitCode Releases. Grant permissions for the chosen operations |
| `GITHUB_ACTIONS_TOKEN` | dev webhook dispatch, stored in dev Cloudflare bindings |
| `WEBHOOK_PASSWORD` | dev webhook authentication, stored in Cloudflare bindings |
| `TRAE_CN_PAT` | Enterprise TRAE CLI login |
| `TRAE_CN_HOST` | Optional enterprise API host variable |
| `CATLASS_DEPLOY_KEY` | Writing the GitHub mirror |
| PyPI Trusted Publisher | Stable PyPI publication, bound to the `pypi` environment and release workflow |

Pass tokens as secrets to the steps that need them. Do not put them in source, prompts or literal example values.
