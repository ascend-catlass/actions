# Workflow guide

[中文](../zh/workflows.md) · [English](../en/workflows.md)

## Five community workflows

| Entry | Trigger | Result |
| --- | --- | --- |
| `reply-atomgit-issue.yml` · Community 1 | New/reopened public Issue by a non-role author, or manual | Short source-based TRAE CN analysis |
| `reply-atomgit-ci-passed.yml` · Community 2 | Passed label added to an open PR, or manual | Deduplicated reminder for PRs by every author |
| `fix-atomgit-issue.yml` · Community 3 | Manual only | Verified small patch, fork PR and `compile` comment |
| `review-atomgit-pr.yml` · Community 4 | Manual only | Evidence-based inline questions on changed code |
| `label-atomgit-issue.yml` · Community 5 | All new public Issues via hook, or manual | One verified existing Issue-kind label; preserve manual categories |

Community 5 is independent of the reply's author-role filter. It fetches the live
label catalogue, uses the shared AI stage, then adds one category after rechecking
the Issue and preserving all existing labels. See [Issue classification](actions/atomgit-issue-label.md).

Select the entry in GitHub Actions, click **Run workflow**, and choose `main`. The three model tasks reuse [trae-cn](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/traecn), pinned official China enterprise CLI 0.209.1 and DeepSeek-V4.1-Flash.

## 1. Brief Issue analysis

The Action checks the latest community role declarations, skips committer/maintainer authors, reads source and discussion, and publishes or updates one owned reply. Manual input is `issue_url`; `publish=false` analyzes without publication. Current state and discussion are checked again before publishing.

## 2. CI-passed reminder

Manually supply an open PR number. The Action requires its current `ci-pipeline-passed` label before publishing. Every PR author is eligible.

The Action's current-state query is a final publication guard. It scans all ordinary comment pages and posts the review/SIG/Ascend 950 reminder once. Runs for the same PR are serialized.

## 3. Quick simple-Issue fix

Manual inputs: `issue_number` and `validation_command`. This manual task is independent of brief Issue analysis: it needs no prior run or reply, has no author-role restriction, and neither task triggers the other. The workflow pins upstream master and the Issue discussion. TRAE CN reads the source and returns a structured simple/not-simple decision plus a minimal unified patch. Complex or unclear problems end as `needs-human` without a PR.

A separate step checks paths, applies a patch of at most ten files and runs the maintainer-selected command without publishing credentials. Automation configuration, symlinks and submodules cannot be changed by a simple fix. Failed validation stops publication. The runner is disposable Linux without an NPU; include dependency setup and meaningful tests in the command. Device-dependent problems need human handling.

After validation and a fresh discussion check, the publisher pushes a `codex/issue-*` branch to its existing personal CATLASS fork and opens an upstream master PR. It reads the PR back and posts one exact `compile` comment. Retries reuse the owned PR and command. The AtomGit account needs fork push/PR/comment permissions.

## 4. Inline PR review

Manual input: `pr_number`. The workflow pins head and base, then provides source and diff to TRAE CN. At most ten findings are accepted, each on an added/modified line in that pinned diff. No findings means no comments. Head/base changes block publication. Owned matching findings are deduplicated by source revision and content.

Publication uses AtomGit's [inline comment endpoint](https://docs.atomgit.com/en/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-comments/), followed by body, author, path and head read-back. It does not approve or merge PRs. Model and publication evidence is retained for seven days.

## Tests, builds and releases

| Workflow | Purpose / schedule (Asia/Shanghai) |
| --- | --- |
| `test-atomgit-pr.yml` | Manual PR number; selective Ascend 950 tests and RDV status |
| `nightly-dsl-wheel.yml` | Daily 01:00: dual-architecture development wheels and GitHub package index |
| `release-dsl-wheel.yml` | Manual stable-tag validation, wheel build, PyPI and AtomGit release |
| `build-dsl-wheel.yml` | Shared build, called by nightly/release or manually |
| `build-ascendnpu-ir-20261013.yml` | Current NPUIR preparation/archive baseline |
| `build-ascendnpu-ir-20260720.yml` | Legacy NPUIR preparation retained for diagnosis |
| `install-cann-weekly.yml` | Daily 02:00: install the same official build on both CPU architectures |
| `sync-atomgit.yml` | Daily 02:00: mirror AtomGit master and tags to GitHub |

See [build and runner operations](operations.md) and individual [Action guides](index.md). Schedules may queue. Production jobs execute from main; the documentation PR check only tests and builds the site.

## TestPR failure diagnosis

After RDV has started, a failed preparation or test job starts a separate GitHub-hosted diagnostic job. It calls the generic [`analyze-ci-failure`](actions/analyze-ci-failure.md) Action with the run ID and attempt. That Action composes official `actions/github-script` for logs, [`setup-trae-cn`](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/setup-traecn) for installation and `trae-cn` for DeepSeek-V4.1-Flash analysis. A small standalone script extracts and redacts bounded evidence and formats the comment attachment. Issue analysis, fixes and PR review also share the installation Action. No PR source is checked out or executed for diagnosis.

The report job appends cause, log evidence and a next step below the existing RDV Failed run link. Missing logs, invalid model output, timeout or missing artifacts produce an unavailable-analysis note instead; RDV-FAIL is still reported. Success and cancellation comments are unchanged. The optional job has a 12-minute limit and the model a 5-minute budget. The comment attachment is retained for seven days. Only the collector gets Actions read permission; the model receives no publishing token.

## Credentials and rollout

| Configuration | Consumer |
| --- | --- |
| `ATOMGIT_TOKEN` → `GITCODE_TOKEN` fallback | Action context, PR/Issue publication, fork pushes and AtomGit releases |
| `TRAE_CN_PAT` | Official TRAE CN enterprise login in model workflows, including TestPR failure diagnosis |
| `TRAE_CN_HOST` | Optional enterprise API host variable |
| `CATLASS_DEPLOY_KEY` | GitHub mirror writes |
| PyPI Trusted Publisher | Stable release publishing in the pypi environment |

Publishing tokens are not passed into model execution. Submit feature changes through PRs and publish them only after merge.

## Shared Action dependency

General stages come from `yuantao313/actions` at reviewed commit `02defff4ec04b38b33adfaec06bcb1406f5a2150`; RDV status publishing uses fix `02defff4ec04b38b33adfaec06bcb1406f5a2150`. Project workflows check out the same revision into `shared_actions` when CATLASS Python policies need its transport helpers. The directory is ignored locally; shared implementations and their unit tests stay upstream.

Credentials prefer `ATOMGIT_TOKEN`; if it is unset or empty, the existing `GITCODE_TOKEN` is used. Existing installations do not need to rename their secret. The release environment keeps its original identifier `gitcode-release` and its configured permissions. Workflow entry files now use `atomgit` names. The historical NPUIR 20260720 build keeps its diagnostic behavior; only its upstream domain and platform wording change.

## How AI results flow

Issue replies, manual fixes, PR reviews and CI failure analysis share [catlass-ai](actions/catlass-ai.md) for model selection, enterprise host, read-only sandbox and public setup/execution. Downstream stages read the answer and model record from that execution, without configuring a separate attribution model. Fix proposals carry both response and execution record through validation and publication. CLI versions come from setup outputs; the Issue URL default is declared only at dispatch. Checks for target number, source revision, patch and validation command remain to reject stale or mismatched publication.
## Prepare dependencies on one host

Manual runs of `build-ascendnpu-ir-20261013.yml` and `install-cann-weekly.yml`
accept `runner_label` and `target_arch`. Supply a unique custom host label such
as `host-179-223-2-2`, and select `x86_64` or `aarch64`. The worker must also
match `self-hosted`, `Linux` and the corresponding `X64` / `ARM64` label.
Use a label that uniquely identifies the host, not its runner display name.

```sh
gh workflow run install-cann-weekly.yml --repo ascend-catlass/actions --ref main \
  -f runner_label=host-179-223-2-2 -f target_arch=x86_64
gh workflow run build-ascendnpu-ir-20261013.yml --repo ascend-catlass/actions --ref main \
  -f runner_label=host-179-223-2-2 -f target_arch=x86_64 \
  -f branch=feature/regbase -f ref=693abf31f3d88d13d30d9578fcf6513b90c0ee33 \
  -f use_mirror=true -f build_jobs=64
```

Dispatch separately with `host-179-228-2-2` for the second host. Empty
`runner_label` retains both architectures and the original worker pools;
`target_arch` does not filter those default runs. Scheduled CANN runs and
existing reusable NPUIR calls keep their previous defaults. The historical
20260720 diagnostic workflow is unchanged. Both entry points execute only on
`main`.

NPUIR archives remain under `/opt/AscendNPU-IR` on the selected worker; CANN
installs under `/opt/cann_weekly`. The runner user needs Docker access and the
passwordless sudo permissions required by the existing installation steps.
