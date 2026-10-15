# CATLASS Actions

[English](README.en.md) · [中文手册](docs/zh/index.md) · [工作流与使用方法](docs/zh/workflows.md)

本仓库负责 CATLASS 的社区协作、PR 测试、每日构建和版本发布。通用组件引用 [yuantao313/actions](https://github.com/yuantao313/actions)，本仓只维护 CATLASS 业务步骤。

## 四条社区流水线

| 流水线 | 触发方式 | 做什么 |
| --- | --- | --- |
| [1. Issue 简要分析](.github/workflows/reply-atomgit-issue.yml) | 手动；跳过 Committer/维护者作者 | TRAE CN 阅读源码和讨论，发表一条简短分析；重复运行更新自己的回复 |
| [2. PR CI 通过回复](.github/workflows/reply-atomgit-ci-passed.yml) | 手动；发布前检查 `ci-pipeline-passed` 标签 | 面向所有 PR 作者，查重后发送检视、SIG 和 Ascend 950 测试提醒 |
| [3. 简单 Issue 快速修复](.github/workflows/fix-atomgit-issue.yml) | **仅手动**，填写 Issue 编号与验证命令 | TRAE CN 判断是否为简单问题、生成最小补丁；验证通过后推到个人 fork、创建 PR，并评论 `compile` |
| [4. PR 行级检视](.github/workflows/review-atomgit-pr.yml) | **仅手动**，填写 PR 编号 | TRAE CN 检视变更，对有依据的疑问发布行级评论；没有问题就不评论 |

简单分析与手动修复互相独立：修复无需先分析，也不限制作者角色，两条流程不会互相触发。

在 GitHub **Actions** 页选择对应的 `Community 1–4` 工作流，点击 **Run workflow**，选择 `main`。修复命令应是与本 Issue 对应的实际测试，例如 `python3 -m pytest tests/path/to/test_case.py`；执行环境是 GitHub Linux runner，没有 NPU，所需依赖需由验证命令准备。复杂问题或验证失败时不会创建 PR。

Action 在发布前复查 PR/Issue 状态并查重。自动修复发布账号需要已有 `cann/catlass` 的个人 fork 和评论权限。详见[使用方法与运行结果](docs/zh/workflows.md)。

## 测试、构建和发布

| 分类 | 工作流 | 用途与时间（北京时间） |
| --- | --- | --- |
| PR 测试 | [test-atomgit-pr](.github/workflows/test-atomgit-pr.yml) | 手动指定 PR 编号，执行 Ascend 950 测试；失败时用 TRAE CN / DeepSeek 分析日志并附到 RDV 失败评论 |
| 每日构建 | [nightly-dsl-wheel](.github/workflows/nightly-dsl-wheel.yml) | 每日 01:00，构建双架构 DSL wheel，发布到 GitHub 包索引 |
| 稳定发布 | [release-dsl-wheel](.github/workflows/release-dsl-wheel.yml) | 手动校验版本 tag，构建并发布 PyPI、AtomGit Release |
| 公共构建 | [build-dsl-wheel](.github/workflows/build-dsl-wheel.yml) | 被 nightly/release 复用，也可手动构建 |
| NPUIR 依赖 | [20261013](.github/workflows/build-ascendnpu-ir-20261013.yml) / [20260720 旧版](.github/workflows/build-ascendnpu-ir-20260720.yml) | 按源码与架构准备归档；**旧版保留用于定位问题** |
| 环境维护 | [install-cann-weekly](.github/workflows/install-cann-weekly.yml) | 每日 02:00，安装同一 CANN weekly 构建到双架构主机 |
| 镜像同步 | [sync-atomgit](.github/workflows/sync-atomgit.yml) | 每日 02:00，同步 AtomGit master 与 tags 到 GitHub |

构建环境、归档目录、镜像、依赖和发布权限见[运维说明](docs/en/operations.md)。定时任务可能排队。

## 可复用 Actions 分类

| 分类 | Actions |
| --- | --- |
| 社区协作 | [TRAE CN](https://github.com/yuantao313/actions/tree/4042e6e501fab8a2cee4e87fca0248b2347e05df/traecn)、[Issue 上下文与回复](.github/actions/atomgit-issue/README.md)、[CI 通过提醒](.github/actions/atomgit-ci-passed/README.md)、[社区角色](.github/actions/community-repo-roles/README.md) |
| PR 测试 | [PR 元数据](https://github.com/yuantao313/actions/tree/4042e6e501fab8a2cee4e87fca0248b2347e05df/atomgit-pr-metadata)、[创建容器](.github/actions/create-ascend-container/README.md)、[测试准备](.github/actions/prepare-ci-tests/README.md)、[运行测试](.github/actions/run-ci-tests/README.md)、[RDV 状态](.github/actions/rdv-status/README.md) |
| 构建与分发 | [NPUIR 本机归档](.github/actions/npuir-local-archive/README.md)、[AtomGit Release](.github/actions/atomgit-release/README.md) |
| 分析与运行环境 | [CI 失败分析](.github/actions/analyze-ci-failure/README.md)、[安装 TRAE CN](https://github.com/yuantao313/actions/tree/4042e6e501fab8a2cee4e87fca0248b2347e05df/setup-traecn) |
| 通用接口 | [AtomGit API](https://github.com/yuantao313/actions/tree/4042e6e501fab8a2cee4e87fca0248b2347e05df/atomgit-api) |

每个 Action 都有中英文用途说明、输入输出和调用示例。四条业务流水线复用这些组件，不把每条流程都重复实现成独立工具。

## 配置与维护

- 社区流程优先使用 `ATOMGIT_TOKEN`，为空时回退到原有 `GITCODE_TOKEN`，无需重建已有 Secret；模型流程（含 TestPR 失败分析）另需 `TRAE_CN_PAT`，可选变量 `TRAE_CN_HOST`。
- 构建、发布与镜像所需配置见[工作流说明](docs/zh/workflows.md)和[运维说明](docs/en/operations.md)。
- 功能修改通过分支 PR 审查后合入，**不直接推主分支**。PR 检查只运行测试和文档构建，不发表社区评论。

本地检查和预览文档：

```text
python -m pip install -r requirements-docs.txt
git clone https://github.com/yuantao313/actions.git shared_actions
git -C shared_actions checkout 4042e6e501fab8a2cee4e87fca0248b2347e05df
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_docs.py
python -m mkdocs build --strict
python -m mkdocs serve
```

完整测试包含 Bash/Linux 用例；GitHub PR 检查在 Linux 执行。文档构建产物是 `site/`，CI 提供下载，不自动发布 Pages。
