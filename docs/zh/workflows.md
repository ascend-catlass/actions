# 工作流怎样串联 Actions

[中文](../zh/workflows.md) · [English](../en/workflows.md)

Action 完成一个可复用步骤，工作流把多个步骤排成完整流程。下面介绍仓库现有的业务工作流；CANN 安装、镜像同步等流程直接调用脚本，没有额外封装为自定义 Action。

## 工作流目录

| 工作流 | 做什么 | 什么时候运行 |
| --- | --- | --- |
| [test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml) | 合并并测试 GitCode PR，再写回 RDV 状态 | 手动；dev webhook 收到白名单账号的 `compile` 或 `rdvcompile` 评论也会触发 |
| [test-gitcode-pr-cann-9-2-beta-2.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr-cann-9-2-beta-2.yml) | 同一套 PR 测试的版本命名入口 | 手动 |
| [reply-gitcode-ci-passed.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-ci-passed.yml) | CI 通过后发送检视提醒 | 手动；dev webhook 收到通过标签事件也会触发 |
| [reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml) | 按作者角色分配 Issue，或分析并回复 | 手动，`publish` 默认开启 |
| [trae-cn-smoke.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/trae-cn-smoke.yml) | 验证 TRAE 适配层和真实 CLI 执行 | 手动 |
| [build-ascendnpu-ir-20261013.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20261013.yml) | 准备当前日期基线的 NPUIR 依赖归档 | 手动或被其他工作流调用 |
| [build-ascendnpu-ir-20260720.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20260720.yml) | 准备较早日期基线的 NPUIR 归档 | 手动或被其他工作流调用 |
| [migrate-npuir-cache.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/migrate-npuir-cache.yml) | 把已完成的旧缓存迁入日期归档，不重新编译 | 手动，选择 `20261013` 或 `20260720` |
| [build-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-dsl-wheel.yml) | 构建 x86_64、aarch64 的 DSL wheel 并保存产物 | 手动或被 nightly/release 调用 |
| [nightly-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/nightly-dsl-wheel.yml) | 构建开发版本并发布到 GitHub Release 支撑的包索引 | 每日北京时间 01:00，或手动 |
| [release-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/release-dsl-wheel.yml) | 校验稳定 tag，构建并发布到 PyPI 与 GitCode Release | 手动 |
| [install-cann-weekly.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/install-cann-weekly.yml) | 安装同一构建版本的 CANN weekly 到两种 CPU 架构主机 | 每日北京时间 02:00，或手动 |
| [sync-gitcode.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/sync-gitcode.yml) | 把 GitCode `master` 与 tags 镜像同步到 GitHub | 每日北京时间 02:00，或手动 |

定时表达式使用 UTC；表格已换算为北京时间。定时任务的实际启动可能排队。仓库的执行 job 均要求 `main` 分支，手动选择其他分支不会执行这些 job。

## PR 测试

1. [gitcode-pr-metadata](actions/gitcode-pr-metadata.md) 查询 PR 分支和来源提交。
2. [rdv-status](actions/rdv-status.md) 写入测试开始状态。
3. GitHub-hosted runner 下载目标分支与 PR，按修改路径分类。只有文档或图片变更时在此完成，不调度 Ascend 950。
4. 代码变更交给 `ascend950` 自托管 runner 合并。获取到的 PR head 与查询结果不同或合并冲突时会失败。
5. [create-ascend-container](actions/create-ascend-container.md) 准备环境；[prepare-ci-tests](actions/prepare-ci-tests.md) 安装过滤后的依赖并选卡。
6. [run-ci-tests](actions/run-ci-tests.md) 执行所需阶段：DSL 依次进行 dev 构建、IR/Lit 测试和设备测试；非 DSL 按变更与反向头文件依赖选择测试。两类都修改则两类都运行。
7. 报告 job 写回 RDV 结果。容器清理由 `always()` 步骤处理。

减少重复工作的方式是共用准备步骤、复用 DSL dev 构建、按变更选择测试，以及把日志链接自动写回 PR。测试选择范围见[源码说明](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md)。

## CI 通过后的提醒

这条流程独立于 RDV 测试。dev 收到 `ci-pipeline-passed` 标签事件后调用工作流；[gitcode-ci-passed](actions/gitcode-ci-passed.md) 再查询当前 PR，确认仍符合条件，分页查重后发送检视提醒。同一 PR 的运行串行执行。

dev 只需要 GitHub 调度凭据；GitCode 查询和评论凭据保存在 actions 仓的 Secret 中。

## Issue 分配与分析

1. 读取作者平台账号，并用 [community-repo-roles](actions/community-repo-roles.md) 查询该仓库的维护者与 Committer。
2. 若作者是声明的角色成员，跳过模型分析，通过 [gitcode-issue](actions/gitcode-issue.md) 发送 `/assign @author-login` 评论。重复运行复用相同的本账号分配评论。
3. 其他符合条件的 Issue 先准备源码和讨论上下文，再通过 [trae-cn](actions/trae-cn.md) 只读分析。
4. 发布前重新检查 Issue、讨论和作者资格。答复变旧时不发布；正常时新建或更新本账号的自动评论，并回查结果。

工作流使用 `DeepSeek-V4.1-Flash`，模型答复末尾署名与模型保持一致。`publish=false` 会停止回复和分配评论的发布。当前是手动入口，没有订阅所有 Issue 自动触发。

## 依赖归档与 wheel 分发

NPUIR 在每台 `publish` 构建机上保留日期归档。[npuir-local-archive](actions/npuir-local-archive.md) 先检查源码提交、架构与构建约定；命中时直接复用，缺失时由工作流编译。`latest` 只前移，wheel 构建仍选择匹配 CATLASS gitlink 的准确依赖。

wheel 工作流在 x86_64 和 aarch64 主机上构建。nightly 发布开发版本到 GitHub 包索引；release 先检查 GitCode 稳定 tag，再发布到 PyPI 和 GitCode。GitCode 分发使用 [gitcode-release](actions/gitcode-release.md)，已有相同附件可复用；`artifact_run_id` 可选择已有发布运行的验证产物，避免重新构建。

## 环境安装与镜像同步

CANN weekly 流程先锁定同一官方构建，再分别在 X64 和 ARM64 `bz` 主机安装 Toolkit 与对应芯片的 ops。安装路径为 `/opt/cann_weekly/YYYYMMDD`；已成功的日期安装会跳过，`latest` 指向完成目录。安装不会更新驱动或固件，日志保存 30 天。

镜像同步从 `cann/catlass` 的 GitCode 仓库拉取 `master` 和 tags，然后强制更新 GitHub `ascend-catlass/catlass` 对应分支与标签，包括清理不再存在的 tag。因此应把目标仓库作为镜像使用。

## 使用时需要哪些凭据

| 凭据或配置 | 使用流程 |
| --- | --- |
| `GITCODE_TOKEN` | PR 元数据、评论和标签；Issue 读取与发布；GitCode Release。按使用范围授予权限 |
| `GITHUB_ACTIONS_TOKEN` | dev webhook 调度本仓库工作流，保存在 dev 的 Cloudflare 绑定中 |
| `WEBHOOK_PASSWORD` | dev webhook 入站鉴权，保存在 Cloudflare 绑定中 |
| `TRAE_CN_PAT` | TRAE CLI 企业登录 |
| `TRAE_CN_HOST` | 可选的企业服务地址变量 |
| `CATLASS_DEPLOY_KEY` | 写入 GitHub 镜像仓库 |
| PyPI Trusted Publisher | 稳定版本的 PyPI 发布，绑定 `pypi` 环境与 release 工作流 |

Token 通过 Secret 传给需要它的步骤；不要放进源码、提示词或调用示例中的普通文本。
