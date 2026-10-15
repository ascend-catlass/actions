# Automation overview

[中文](../zh/index.md) · [English](../en/index.md)

The four community workflows provide brief Issue analysis, CI-passed reminders, manual simple-Issue fixes and manual inline PR review. The three analysis/fix/review tasks use TRAE CN. See [workflow instructions](workflows.md) for triggers, inputs and publication rules.

PR tests, daily builds, releases, environment maintenance and historical NPUIR diagnosis remain separate. See [build operations](operations.md) for runner setup.

## Reusable Actions by purpose

| Category | Actions |
| --- | --- |
| Community | [trae-cn](actions/trae-cn.md), [gitcode-issue](actions/gitcode-issue.md), [gitcode-ci-passed](actions/gitcode-ci-passed.md), [community-repo-roles](actions/community-repo-roles.md) |
| PR tests | [gitcode-pr-metadata](actions/gitcode-pr-metadata.md), [create-ascend-container](actions/create-ascend-container.md), [prepare-ci-tests](actions/prepare-ci-tests.md), [run-ci-tests](actions/run-ci-tests.md), [rdv-status](actions/rdv-status.md) |
| Build / release | [npuir-local-archive](actions/npuir-local-archive.md), [gitcode-release](actions/gitcode-release.md) |
| Analysis / runtime | [analyze-ci-failure](actions/analyze-ci-failure.md), [setup-trae-cn](actions/setup-trae-cn.md) |
| Shared transport | [gitcode-api](actions/gitcode-api.md) |

Each page explains purpose, prerequisites, inputs, outputs and a YAML steps example. The fourteen reusable Actions form larger workflows; a workflow is not counted as another Action. Features are submitted through PRs, and automation does not merge or approve PRs.
