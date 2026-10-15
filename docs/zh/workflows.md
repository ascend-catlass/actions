# 工作流怎样串联 Actions

[中文](../zh/workflows.md) · [English](../en/workflows.md)

Action 完成一个可复用步骤，工作流把多个步骤排成完整流程。下面介绍仓库现有的业务工作流；CANN 安装、镜像同步等流程直接调用脚本，没有额外封装为自定义 Action。

## 工作流目录

| 工作流 | 做什么 | 什么时候运行 |
| --- | --- | --- |
| [test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml) | 合并并测试 GitCode PR，再写回 RDV 状态 | 手动；dev webhook 收到白名单账号的 `compile` 或 `rdvcompile` 评论也会触发 |
| [reply-gitcode-ci-passed.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-ci-passed.yml) | CI 通过后发送检视提醒 | 手动；dev webhook 收到通过标签事件也会触发 |
| [reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml) | 非角色成员 Issue 简要分析（TRAE CN） | 新建/重开 hook 或手动 |
| [fix-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/fix-gitcode-issue.yml) | 简单 Issue 修复、提 PR、评论 compile（TRAE CN） | 仅手动 |
| [review-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/review-gitcode-pr.yml) | 对变更行发布检视意见（TRAE CN） | 仅手动 |
| [build-ascendnpu-ir-20261013.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20261013.yml) | 准备当前日期基线的 NPUIR 依赖归档 | 手动或被其他工作流调用 |
| [build-ascendnpu-ir-20260720.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20260720.yml) | 保留旧 NPUIR 日期基线，供历史问题定位 | 手动或被其他工作流调用 |
| [build-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-dsl-wheel.yml) | 构建 x86_64、aarch64 的 DSL wheel 并保存产物 | 手动或被 nightly/release 调用 |
| [nightly-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/nightly-dsl-wheel.yml) | 构建开发版本并发布到 GitHub Release 支撑的包索引 | 每日北京时间 01:00，或手动 |
| [release-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/release-dsl-wheel.yml) | 校验稳定 tag，构建并发布到 PyPI 与 GitCode Release | 手动 |
| [install-cann-weekly.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/install-cann-weekly.yml) | 安装同一构建版本的 CANN weekly 到两种 CPU 架构主机 | 每日北京时间 02:00，或手动 |
| [sync-gitcode.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/sync-gitcode.yml) | 把 GitCode `master` 与 tags 镜像同步到 GitHub | 每日北京时间 02:00，或手动 |

定时表达式使用 UTC；表格已换算为北京时间。定时任务的实际启动可能排队。业务 job 均要求 `main` 分支，手动选择其他分支不会执行业务任务。PR 检查只测试和构建文档，不发布评论。

## PR 测试

1. [gitcode-pr-metadata](actions/gitcode-pr-metadata.md) 查询 PR 分支和来源提交。
2. [rdv-status](actions/rdv-status.md) 写入测试开始状态。
3. GitHub-hosted runner 下载目标分支与 PR，按修改路径分类。只有文档或图片变更时在此完成，不调度 Ascend 950。
4. 代码变更交给 `ascend950` 自托管 runner 合并。获取到的 PR head 与查询结果不同或合并冲突时会失败。
5. [create-ascend-container](actions/create-ascend-container.md) 准备环境；[prepare-ci-tests](actions/prepare-ci-tests.md) 安装过滤后的依赖并选卡。
6. [run-ci-tests](actions/run-ci-tests.md) 执行所需阶段：DSL 依次进行 dev 构建、IR/Lit 测试和设备测试；非 DSL 按变更与反向头文件依赖选择测试。两类都修改则两类都运行。
7. 已启动 RDV 后，准备阶段或测试 job 失败会启动独立的 GitHub 托管分析 job：用官方 `actions/github-script` 的 Octokit 客户端读取当前 run attempt 的失败阶段及 job 日志，不再自写 Python API 脚本；提取首批错误和日志尾部，经脱敏与长度限制后交给 TRAE CN / DeepSeek-V4.1-Flash，输出原因、依据和下一步建议。不检出或执行 PR 代码。
8. 报告 job 将分析追加在原 RDV Failed 评论的运行链接下；分析 job 超时、模型失败或日志不可用时附加“分析暂不可用”，仍正常发布 RDV-FAIL。成功与取消的评论保持原样。分析 job 最长 12 分钟，模型执行预算 5 分钟；评论附件保存七天。容器清理由 `always()` 步骤处理。

减少重复工作的方式是共用准备步骤、复用 DSL dev 构建、按变更选择测试，以及把日志链接自动写回 PR。测试选择范围见[源码说明](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md)。

## 四条社区协作流水线

### 1. Issue 简要分析（自动，TRAE CN）

dev 收到公开 Issue 新建/重开事件，按原生作者账号和社区角色名单筛选；非 Committer/维护者才调度 `reply-gitcode-issue.yml`。Action 从社区仓库再次读取最新角色声明，角色成员跳过分析，也不自动分配。其余 Issue 读取源码和讨论，TRAE CN 使用 DeepSeek-V4.1-Flash 给出简短分析；发布前检查讨论是否变化，更新或创建本账号的一条回复。

手动补跑：选择 **Community 1**，填写 `issue_url`。`publish=false` 只生成分析，不发评论。结果保留七天。

### 2. PR CI 通过后回复（自动，所有 PR）

dev 只检查事件：PR 开启，当前标签含 `ci-pipeline-passed`，且 previous 不含该标签，才调度 `reply-gitcode-ci-passed.yml`。**不查询 CI，不因运行中或空标签启动 Action。** 未携带标签的投递直接忽略，需检查发送端配置或手动补跑。PR 作者角色不影响回复资格。

Action 查询当前状态、分页查重并发送检视提醒；同一 PR 串行执行。这里的查询用于发布前防止状态变化。手动补跑：选择 **Community 2**，填写 `pr_number`。

### 3. 简单 Issue 快速修复（仅手动，TRAE CN）

选择 **Community 3**，填写 `issue_number` 与 `validation_command`。这是独立的维护者手动任务，与简要分析回复没有依赖或互相触发关系；无需先分析、不要求已有回复，也不限制 Issue 作者角色。

1. 固定 CATLASS master 源码和 Issue 讨论快照。
2. TRAE CN 只读分析根因，输出是否简单、修复说明与 unified patch。复杂或不明确的问题结束为 `needs-human`，不提 PR。
3. 独立步骤校验并应用补丁，最多十个文件，不接受自动化配置、symlink 或子模块修改；执行维护者指定验证命令。验证步骤不接收发布凭据。
4. 验证通过且讨论未变化，推送至发布账号已有的 CATLASS 个人 fork 的 `codex/issue-*` 分支，再向 `cann/catlass:master` 提 PR。
5. 回查 PR 后发布一条准确的 `compile` 评论，触发既有测试；重试时复用已创建的 PR 和评论。

运行环境是 GitHub Linux runner，无 NPU。验证命令需包含必要依赖准备，并应覆盖这个修复；例如 `python3 -m pytest tests/path/to/test_case.py`。需要设备才能确认的问题交由人工处理。发布账号的 GitCode Token 需有 fork 推送、创建 PR 和评论权限，且账号必须在 dev 的 `compile` 白名单。

### 4. PR 行级检视（仅手动，TRAE CN）

选择 **Community 4**，填写 `pr_number`。固定 PR head/base，读取 diff 和相关源码。模型只返回有代码依据的疑问，最多十条；发布程序要求每条对应当前 diff 的新增/修改行，不能把普通评论当作行级检视。PR 更新后拒绝发布，需重新运行；相同版本、相同问题重试不重复评论。无发现时正常结束，不发布评论，也不自动批准或合并。

使用 GitCode [行级评论接口](https://docs.gitcode.com/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-comments/)，发布后回查评论正文、作者、文件与 head。分析和发布证据保留七天。

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
| `TRAE_CN_PAT` | TRAE CLI 企业登录，包含 TestPR 失败分析 |
| `TRAE_CN_HOST` | 可选的企业服务地址变量 |
| `CATLASS_DEPLOY_KEY` | 写入 GitHub 镜像仓库 |
| PyPI Trusted Publisher | 稳定版本的 PyPI 发布，绑定 `pypi` 环境与 release 工作流 |

Token 通过 Secret 传给需要它的步骤；不要放进源码、提示词或调用示例中的普通文本。
