# CATLASS Actions

[中文](README.md) · [English guide](docs/en/index.md) · [Workflow instructions](docs/en/workflows.md)

CATLASS community collaboration, PR testing, daily builds and releases share reusable Actions in this repository.

## Four community workflows

| Workflow | Trigger | Result |
| --- | --- | --- |
| [1. Brief Issue analysis](.github/workflows/reply-gitcode-issue.yml) | dev hook: new/reopened public Issues by non-committers/non-maintainers; manual fallback | TRAE CN reads source and discussion, then creates or updates one short reply |
| [2. CI-passed PR reminder](.github/workflows/reply-gitcode-ci-passed.yml) | dev hook: passed label added to an open PR; manual fallback | One deduplicated review, SIG and Ascend 950 reminder for PRs by all authors |
| [3. Quick fix for a simple Issue](.github/workflows/fix-gitcode-issue.yml) | **Manual only**: Issue number and validation command | TRAE CN proposes a small patch; verified changes go to the account's personal fork, then a PR and a `compile` comment |
| [4. Inline PR review](.github/workflows/review-gitcode-pr.yml) | **Manual only**: PR number | TRAE CN posts evidence-based questions on changed code lines; no findings means no comments |

Brief analysis and manual fixes are independent: no prerequisite reply, no author-role restriction for fixes, and no cross-triggering.

Choose a `Community 1–4` workflow in GitHub Actions, click **Run workflow**, and select `main`. Fix validation runs on a disposable Linux runner without an NPU. Supply the actual test command and dependency setup relevant to the Issue. Complex Issues and failed verification do not produce PRs.

The dev gateway authenticates and filters native events only. A PR event without the passed label does not start a workflow; the gateway does not query CI. Issue authors are checked against a small community role list. Actions own analysis, current-state rechecks, deduplication and publication. Configure GitCode to send Issue, Pull Request and Note hooks, including labels on label updates. The publishing account must have a verified CATLASS fork and permission to trigger `compile`.

## Testing, builds and releases

| Category | Workflow | Purpose / schedule (Asia/Shanghai) |
| --- | --- | --- |
| PR testing | [test-gitcode-pr](.github/workflows/test-gitcode-pr.yml) | Manual or allowlisted `compile` / `rdvcompile`; Ascend 950 validation and RDV status |
| Daily build | [nightly-dsl-wheel](.github/workflows/nightly-dsl-wheel.yml) | Daily 01:00; dual-architecture wheels and GitHub package index |
| Stable release | [release-dsl-wheel](.github/workflows/release-dsl-wheel.yml) | Manual tag validation, wheel build, PyPI and GitCode publication |
| Shared wheel build | [build-dsl-wheel](.github/workflows/build-dsl-wheel.yml) | Shared nightly/release build, also manual |
| NPUIR dependencies | [20261013](.github/workflows/build-ascendnpu-ir-20261013.yml) / [legacy 20260720](.github/workflows/build-ascendnpu-ir-20260720.yml) | Source/architecture-specific archives; legacy entry retained for diagnosis |
| Environment | [install-cann-weekly](.github/workflows/install-cann-weekly.yml) | Daily 02:00; install the same weekly build on both architectures |
| Mirror | [sync-gitcode](.github/workflows/sync-gitcode.yml) | Daily 02:00; mirror GitCode master and tags |

Schedules may queue. See [runner and build operations](docs/en/operations.md) for images, paths, dependencies and release credentials.

## Reusable Actions by purpose

| Category | Actions |
| --- | --- |
| Community | [trae-cn](.github/actions/trae-cn/README.md), [gitcode-issue](.github/actions/gitcode-issue/README.md), [gitcode-ci-passed](.github/actions/gitcode-ci-passed/README.md), [community-repo-roles](.github/actions/community-repo-roles/README.md) |
| PR testing | [gitcode-pr-metadata](.github/actions/gitcode-pr-metadata/README.md), [create-ascend-container](.github/actions/create-ascend-container/README.md), [prepare-ci-tests](.github/actions/prepare-ci-tests/README.md), [run-ci-tests](.github/actions/run-ci-tests/README.md), [rdv-status](.github/actions/rdv-status/README.md) |
| Build / delivery | [npuir-local-archive](.github/actions/npuir-local-archive/README.md), [gitcode-release](.github/actions/gitcode-release/README.md) |
| Shared API | [gitcode-api](.github/actions/gitcode-api/README.md) |

Each Action has bilingual usage, input/output and example documentation.

## Configuration and contribution

Community workflows use `GITCODE_TOKEN`; model workflows also use `TRAE_CN_PAT` and optional `TRAE_CN_HOST`. See the [workflow guide](docs/en/workflows.md) for details. Submit feature branches as PRs instead of pushing main. PR checks run tests and build documentation without publishing comments. Merge actions first, then merge and deploy dev.

```text
python -m pip install -r requirements-docs.txt
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_docs.py
python -m mkdocs build --strict
python -m mkdocs serve
```

Full tests include Bash/Linux cases. The built site is `site/`; CI uploads it as an artifact without publishing Pages.
