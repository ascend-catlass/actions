# CATLASS Actions

[中文](README.md) · [English guide](docs/en/index.md) · [Workflow instructions](docs/en/workflows.md)

This repository owns CATLASS community workflows, PR tests, builds and releases. General stages are consumed from [yuantao313/actions](https://github.com/yuantao313/actions); only project policies and hardware stages are maintained here.

## Four community workflows

| Workflow | Trigger | Result |
| --- | --- | --- |
| [1. Issue analysis and classification](.github/workflows/reply-atomgit-issue.yml) | Hook and manual recovery | One AI execution classifies every author and produces source-grounded replies for non-role authors |
| [2. CI-passed PR reminder](.github/workflows/reply-atomgit-ci-passed.yml) | Manual; verify the passed label before publication | One deduplicated review, SIG and Ascend 950 reminder for PRs by all authors |
| [3. Quick fix for a simple Issue](.github/workflows/fix-atomgit-issue.yml) | **Manual only**: Issue number and validation command | TRAE CN proposes a small patch; verified changes go to the account's personal fork, then a PR and a `compile` comment |
| [4. Inline PR review](.github/workflows/review-atomgit-pr.yml) | **Manual only**: PR number | TRAE CN posts evidence-based questions on changed code lines; no findings means no comments |

Brief analysis and manual fixes are independent: no prerequisite reply, no author-role restriction for fixes, and no cross-triggering.

Choose a `Community 1–4` workflow in GitHub Actions, click **Run workflow**, and select `main`. Fix validation runs on a disposable Linux runner without an NPU. Supply the actual test command and dependency setup relevant to the Issue. Complex Issues and failed verification do not produce PRs.

Actions recheck current state and deduplicate before publication. The publishing account needs a verified CATLASS fork and permission to comment.

## Testing, builds and releases

| Category | Workflow | Purpose / schedule (Asia/Shanghai) |
| --- | --- | --- |
| PR testing | [test-atomgit-pr](.github/workflows/test-atomgit-pr.yml) | Manual PR number; Ascend 950 validation and RDV status; TRAE CN / DeepSeek adds log analysis to failure comments |
| Daily build | [nightly-dsl-wheel](.github/workflows/nightly-dsl-wheel.yml) | Daily 01:00; dual-architecture wheels and GitHub package index |
| Stable release | [release-dsl-wheel](.github/workflows/release-dsl-wheel.yml) | Manual tag validation, wheel build, PyPI and AtomGit publication |
| Shared wheel build | [build-dsl-wheel](.github/workflows/build-dsl-wheel.yml) | Shared nightly/release build, also manual |
| NPUIR dependencies | [20261013](.github/workflows/build-ascendnpu-ir-20261013.yml) / [legacy 20260720](.github/workflows/build-ascendnpu-ir-20260720.yml) | Source/architecture-specific archives; legacy entry retained for diagnosis |
| Environment | [install-cann-weekly](.github/workflows/install-cann-weekly.yml) | Daily 02:00; install the same weekly build on both architectures |
| Mirror | [sync-atomgit](.github/workflows/sync-atomgit.yml) | Daily 02:00; mirror AtomGit master and tags |

Schedules may queue. See [runner and build operations](docs/en/operations.md) for images, paths, dependencies and release credentials.

## Reusable Actions by purpose

| Category | Actions |
| --- | --- |
| Community | [trae-cn](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/traecn), [atomgit-issue](.github/actions/atomgit-issue/README.md), [atomgit-ci-passed](.github/actions/atomgit-ci-passed/README.md), [community-repo-roles](.github/actions/community-repo-roles/README.md) |
| PR testing | [atomgit-pr-metadata](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/atomgit-pr-metadata), [create-ascend-container](.github/actions/create-ascend-container/README.md), [prepare-ci-tests](.github/actions/prepare-ci-tests/README.md), [run-ci-tests](.github/actions/run-ci-tests/README.md), [rdv-status](.github/actions/rdv-status/README.md) |
| Build / delivery | [npuir-local-archive](.github/actions/npuir-local-archive/README.md), [atomgit-release](.github/actions/atomgit-release/README.md) |
| Analysis / runtime | [catlass-ai](.github/actions/catlass-ai/README.md), [analyze-ci-failure](.github/actions/analyze-ci-failure/README.md), [setup-trae-cn](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/setup-traecn) |
| Shared API | [atomgit-api](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/atomgit-api) |

Each Action has bilingual usage, input/output and example documentation.

## Configuration and contribution

Community workflows prefer `ATOMGIT_TOKEN` and fall back to the existing `GITCODE_TOKEN` when empty; no existing secret needs to be recreated. Model workflows (including TestPR failure diagnosis) also use `TRAE_CN_PAT` and optional `TRAE_CN_HOST`. See the [workflow guide](docs/en/workflows.md) for details. Submit feature branches as PRs instead of pushing main. PR checks run tests and build documentation without publishing comments.

```text
python -m pip install -r requirements-docs.txt
git clone https://github.com/yuantao313/actions.git shared_actions
git -C shared_actions checkout 02defff4ec04b38b33adfaec06bcb1406f5a2150
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_docs.py
python -m mkdocs build --strict
python -m mkdocs serve
```

Full tests include Bash/Linux cases. The built site is `site/`; CI uploads it as an artifact without publishing Pages.
