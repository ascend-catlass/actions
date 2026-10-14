# Automation overview

[中文](../zh/index.md) · [English](../en/index.md)

This repository packages repeated PR testing, environment setup, community collaboration and release tasks as reusable Actions. Workflows decide when and where to run and how to connect steps; each Action performs a concrete task.


## Find the Action you need

| Action | What it does |
| --- | --- |
| [community-repo-roles](actions/community-repo-roles.md) | Look up community maintainers and committers |
| [create-ascend-container](actions/create-ascend-container.md) | Create an Ascend test container |
| [gitcode-api](actions/gitcode-api.md) | Call the GitCode API |
| [gitcode-ci-passed](actions/gitcode-ci-passed.md) | Send a review reminder after CI passes |
| [gitcode-issue](actions/gitcode-issue.md) | Prepare, reply to or assign a GitCode Issue |
| [gitcode-pr-metadata](actions/gitcode-pr-metadata.md) | Read and validate PR metadata |
| [gitcode-release](actions/gitcode-release.md) | Publish a GitCode release bundle |
| [npuir-local-archive](actions/npuir-local-archive.md) | Reuse local AscendNPU-IR build archives |
| [prepare-ci-tests](actions/prepare-ci-tests.md) | Prepare test dependencies and select an NPU |
| [rdv-status](actions/rdv-status.md) | Report RDV test status on a PR |
| [run-ci-tests](actions/run-ci-tests.md) | Run a CATLASS test stage |
| [trae-cn](actions/trae-cn.md) | Run a TRAE CN analysis task |

## How the steps fit together

1. PR testing: read revisions → report start → prepare the environment and select a device → run tests → report results.
2. CI-passed reminder: dev webhook dispatch → read current PR state → check existing comments → post a review reminder.
3. Issue collaboration: check author and community roles → assign role-member Issues, or prepare context → analyze → publish a reply.
4. Version builds: reuse or build an NPUIR archive → build wheels on two CPU architectures → validate and distribute.

See [the workflow guide](workflows.md) for triggers, schedules and runners.


## Reading the examples

Each YAML example is a steps excerpt for an existing workflow job. `${{ secrets.NAME }}` reads a GitHub secret, while `${{ steps.xxx.outputs.yyy }}` references an earlier step output. Match example numbers, paths and step names to the actual task.

Examples reference @main to follow the current repository. Callers needing a fixed release can use a verified full commit SHA. Each action.yml defines the public interface.


## Current scope

The guide covers 12 custom Actions. CANN weekly installation, repository mirroring and full wheel build/distribution are implemented as workflows and scripts; they are covered in the workflow guide rather than counted as extra Actions. The automation does not approve reviews or merge PRs automatically.
