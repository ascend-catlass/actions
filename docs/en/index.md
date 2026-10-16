# Automation overview

[中文](../zh/index.md) · [English](../en/index.md)

The four community workflows provide brief Issue analysis, CI-passed reminders, manual simple-Issue fixes and manual inline PR review. The three analysis/fix/review tasks use TRAE CN. See [workflow instructions](workflows.md) for triggers, inputs and publication rules.

PR tests, daily builds, releases, environment maintenance and historical NPUIR diagnosis remain separate. See [build operations](operations.md) for runner setup.

## Reusable Actions by purpose

| Category | Actions |
| --- | --- |
| Community | [trae-cn](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/traecn), [atomgit-issue](actions/atomgit-issue.md), [atomgit-ci-passed](actions/atomgit-ci-passed.md), [community-repo-roles](actions/community-repo-roles.md) |
| PR tests | [atomgit-pr-metadata](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/atomgit-pr-metadata), [create-ascend-container](actions/create-ascend-container.md), [prepare-ci-tests](actions/prepare-ci-tests.md), [run-ci-tests](actions/run-ci-tests.md), [rdv-status](actions/rdv-status.md) |
| Build / release | [npuir-local-archive](actions/npuir-local-archive.md), [atomgit-release](actions/atomgit-release.md) |
| Analysis / runtime | [catlass-ai](actions/catlass-ai.md), [analyze-ci-failure](actions/analyze-ci-failure.md), [setup-trae-cn](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/setup-traecn) |
| Shared transport | [atomgit-api](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/atomgit-api) |

Each page explains purpose, prerequisites, inputs, outputs and a YAML steps example. The eleven CATLASS Actions form larger workflows; a workflow is not counted as another Action. Features are submitted through PRs, and automation does not merge or approve PRs.
