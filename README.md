# CATLASS Actions

[English](README.en.md) · [中文手册](docs/zh/index.md) · [工作流与使用方法](docs/zh/workflows.md)

本仓库负责 CATLASS 的社区协作、PR 测试、每日构建和版本发布。社区协作分为下面四条流水线；公共 Action 是它们复用的步骤。

## 四条社区流水线

| 流水线 | 触发方式 | 做什么 |
| --- | --- | --- |
| [1. Issue 简要分析](.github/workflows/reply-gitcode-issue.yml) | dev hook：公开 Issue 新建/重开，作者非 Committer/维护者；也可手动 | TRAE CN 阅读源码和讨论，发表一条简短分析；重复运行更新自己的回复 |
| [2. PR CI 通过回复](.github/workflows/reply-gitcode-ci-passed.yml) | dev hook：开启 PR 新增 `ci-pipeline-passed` 标签；也可手动补跑 | 面向所有 PR 作者，查重后发送检视、SIG 和 Ascend 950 测试提醒 |
| [3. 简单 Issue 快速修复](.github/workflows/fix-gitcode-issue.yml) | **仅手动**，填写 Issue 编号与验证命令 | TRAE CN 判断是否为简单问题、生成最小补丁；验证通过后推到个人 fork、创建 PR，并评论 `compile` |
| [4. PR 行级检视](.github/workflows/review-gitcode-pr.yml) | **仅手动**，填写 PR 编号 | TRAE CN 检视变更，对有依据的疑问发布行级评论；没有问题就不评论 |

简单分析与手动修复互相独立：修复无需先分析，也不限制作者角色，两条流程不会互相触发。

在 GitHub **Actions** 页选择对应的 `Community 1–4` 工作流，点击 **Run workflow**，选择 `main`。修复命令应是与本 Issue 对应的实际测试，例如 `python3 -m pytest tests/path/to/test_case.py`；执行环境是 GitHub Linux runner，没有 NPU，所需依赖需由验证命令准备。复杂问题或验证失败时不会创建 PR。

### dev hook 的边界

hook 只做鉴权和原始事件筛选。PR 事件看标签，不查询 CI：没有通过标签就不调度 GitHub。Issue 事件按原生作者字段和简单社区角色名单过滤。分析、GitCode 查询、发布和查重在 Action 中完成；发布前复查状态，防止分析期间 PR/Issue 已变化。

需要 GitCode webhook 订阅 Issue、Pull Request 和 Note 事件。标签更新必须携带通过标签；空标签事件直接忽略，不为其创建检查流水线。自动修复发布账号须位于 `compile` 白名单，且已有 `cann/catlass` 的个人 fork。详见[使用方法与运行结果](docs/zh/workflows.md)。

## 测试、构建和发布

| 分类 | 工作流 | 用途与时间（北京时间） |
| --- | --- | --- |
| PR 测试 | [test-gitcode-pr](.github/workflows/test-gitcode-pr.yml) | 手动或白名单账号评论 `compile` / `rdvcompile`，执行 Ascend 950 测试；失败时用 TRAE CN / DeepSeek 分析日志并附到 RDV 失败评论 |
| 每日构建 | [nightly-dsl-wheel](.github/workflows/nightly-dsl-wheel.yml) | 每日 01:00，构建双架构 DSL wheel，发布到 GitHub 包索引 |
| 稳定发布 | [release-dsl-wheel](.github/workflows/release-dsl-wheel.yml) | 手动校验版本 tag，构建并发布 PyPI、GitCode Release |
| 公共构建 | [build-dsl-wheel](.github/workflows/build-dsl-wheel.yml) | 被 nightly/release 复用，也可手动构建 |
| NPUIR 依赖 | [20261013](.github/workflows/build-ascendnpu-ir-20261013.yml) / [20260720 旧版](.github/workflows/build-ascendnpu-ir-20260720.yml) | 按源码与架构准备归档；**旧版保留用于定位问题** |
| 环境维护 | [install-cann-weekly](.github/workflows/install-cann-weekly.yml) | 每日 02:00，安装同一 CANN weekly 构建到双架构主机 |
| 镜像同步 | [sync-gitcode](.github/workflows/sync-gitcode.yml) | 每日 02:00，同步 GitCode master 与 tags 到 GitHub |

构建环境、归档目录、镜像、依赖和发布权限见[运维说明](docs/en/operations.md)。定时任务可能排队。

## 可复用 Actions 分类

| 分类 | Actions |
| --- | --- |
| 社区协作 | [TRAE CN](.github/actions/trae-cn/README.md)、[Issue 上下文与回复](.github/actions/gitcode-issue/README.md)、[CI 通过提醒](.github/actions/gitcode-ci-passed/README.md)、[社区角色](.github/actions/community-repo-roles/README.md) |
| PR 测试 | [PR 元数据](.github/actions/gitcode-pr-metadata/README.md)、[创建容器](.github/actions/create-ascend-container/README.md)、[测试准备](.github/actions/prepare-ci-tests/README.md)、[运行测试](.github/actions/run-ci-tests/README.md)、[RDV 状态](.github/actions/rdv-status/README.md) |
| 构建与分发 | [NPUIR 本机归档](.github/actions/npuir-local-archive/README.md)、[GitCode Release](.github/actions/gitcode-release/README.md) |
| 分析与运行环境 | [CI 失败分析](.github/actions/analyze-ci-failure/README.md)、[安装 TRAE CN](.github/actions/setup-trae-cn/README.md) |
| 通用接口 | [GitCode API](.github/actions/gitcode-api/README.md) |

每个 Action 都有中英文用途说明、输入输出和调用示例。四条业务流水线复用这些组件，不把每条流程都重复实现成独立工具。

## 配置与维护

- 社区流程需要 `GITCODE_TOKEN`；模型流程（含 TestPR 失败分析）另需 `TRAE_CN_PAT`，可选变量 `TRAE_CN_HOST`。
- 构建、发布与镜像所需配置见[工作流说明](docs/zh/workflows.md)和[运维说明](docs/en/operations.md)。
- 功能修改通过分支 PR 审查后合入，**不直接推主分支**。PR 检查只运行测试和文档构建，不发表社区评论。
- 先合入 actions 改动，再合入并部署 dev；不要让 hook 调用尚未发布的工作流。

本地检查和预览文档：

```text
python -m pip install -r requirements-docs.txt
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_docs.py
python -m mkdocs build --strict
python -m mkdocs serve
```

完整测试包含 Bash/Linux 用例；GitHub PR 检查在 Linux 执行。文档构建产物是 `site/`，CI 提供下载，不自动发布 Pages。
