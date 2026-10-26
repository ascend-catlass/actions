# 工作流怎样串联 Actions

[中文](../zh/workflows.md) · [English](../en/workflows.md)

Action 完成一个可复用步骤，工作流把多个步骤排成完整流程。下面介绍仓库现有的业务工作流；CANN 安装、镜像同步等流程直接调用脚本，没有额外封装为自定义 Action。

## 工作流目录

| 工作流 | 做什么 | 什么时候运行 |
| --- | --- | --- |
| [test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml) | 合并并测试 AtomGit PR，再写回 RDV 状态 | 手动指定 PR 编号 |
| [reply-atomgit-ci-passed.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-ci-passed.yml) | CI 通过后发送检视提醒 | 手动；检查通过标签 |
| [reply-atomgit-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-issue.yml) | 一次 AI 分类所有作者，为非角色作者回复 | hook 自动；可手动补跑 |
| [fix-atomgit-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/fix-atomgit-issue.yml) | 简单 Issue 修复、提 PR、评论 compile（TRAE CN） | 仅手动 |
| [review-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/review-atomgit-pr.yml) | 对变更行发布检视意见（TRAE CN） | 仅手动 |
| [build-ascendnpu-ir-20261013.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20261013.yml) | 准备当前日期基线的 NPUIR 依赖归档 | 手动或被其他工作流调用 |
| [build-ascendnpu-ir-20260720.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-ascendnpu-ir-20260720.yml) | 保留旧 NPUIR 日期基线，供历史问题定位 | 手动或被其他工作流调用 |
| [build-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/build-dsl-wheel.yml) | 构建 x86_64、aarch64 的 DSL wheel 并保存产物 | 手动或被 nightly/release 调用 |
| [nightly-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/nightly-dsl-wheel.yml) | 构建开发版本并发布到 GitHub Release 支撑的包索引 | 每日北京时间 01:00，或手动 |
| [release-dsl-wheel.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/release-dsl-wheel.yml) | 校验稳定 tag，构建并发布到 PyPI 与 AtomGit Release | 手动 |
| [install-cann-weekly.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/install-cann-weekly.yml) | 安装同一构建版本的 CANN weekly 到全部 11 台主机 | 每日北京时间 02:00，或手动 |
| [sync-atomgit.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/sync-atomgit.yml) | 把 AtomGit `master` 与 tags 镜像同步到 GitHub | 每日北京时间 02:00，或手动 |

定时表达式使用 UTC；表格已换算为北京时间。定时任务的实际启动可能排队。业务 job 均要求 `main` 分支，手动选择其他分支不会执行业务任务。PR 检查只测试和构建文档，不发布评论。

## Issue 自动分类

[Issue 分类 Action](actions/atomgit-issue-label.md) 已合入 Community 1：一次 AI 同时生成分类和分析回复。
所有作者均可分类，只有非角色作者收到分析回复。只追加一个已有类型标签，保留人工分类；不触发手动修复或代码检视。

## PR 测试

1. [atomgit-pr-metadata](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/atomgit-pr-metadata) 查询 PR 分支和来源提交。
2. [rdv-status](actions/rdv-status.md) 写入测试开始状态。
3. GitHub-hosted runner 下载目标分支与 PR，按修改路径分类。只有文档或图片变更时在此完成，不调度 Ascend 950。
4. 代码变更交给 `ascend950` 自托管 runner 合并。获取到的 PR head 与查询结果不同或合并冲突时会失败。
5. [create-ascend-container](actions/create-ascend-container.md) 准备环境；[prepare-ci-tests](actions/prepare-ci-tests.md) 安装过滤后的依赖并选卡。
6. [run-ci-tests](actions/run-ci-tests.md) 执行所需阶段：DSL 依次进行 dev 构建、IR/Lit 测试和设备测试；非 DSL 按变更与反向头文件依赖选择测试。两类都修改则两类都运行。
7. 已启动 RDV 后，准备阶段或测试 job 失败会启动独立的 GitHub 托管分析 job：调用通用的 [`analyze-ci-failure`](actions/analyze-ci-failure.md)，传入当前运行编号与 attempt。Action 内复用官方 `actions/github-script` 获取日志、[`setup-trae-cn`](https://github.com/yuantao313/actions/tree/02defff4ec04b38b33adfaec06bcb1406f5a2150/setup-traecn) 安装 CLI、`trae-cn` 执行 DeepSeek-V4.1-Flash 分析；独立的小脚本负责日志摘取、脱敏和评论组装，输出原因、依据和下一步建议。安装 Action 也供 Issue 分析、修复和 PR 检视共用。不检出或执行 PR 代码。
8. 报告 job 将分析追加在原 RDV Failed 评论的运行链接下；分析 job 超时、模型失败或日志不可用时附加“分析暂不可用”，仍正常发布 RDV-FAIL。成功与取消的评论保持原样。分析 job 最长 12 分钟，模型执行预算 5 分钟；评论附件保存七天。容器清理由 `always()` 步骤处理。

减少重复工作的方式是共用准备步骤、复用 DSL dev 构建、按变更选择测试，以及把日志链接自动写回 PR。测试选择范围见[源码说明](https://github.com/ascend-catlass/actions/blob/main/.github/actions/run-ci-tests/SOURCE.md)。

## 四条社区协作流水线

### 1. Issue 分析与分类（自动，TRAE CN）

Action 读取已有类型标签和最新社区角色声明。一次 AI 为所有作者选择合适标签，并为非 Committer/维护者作者读取源码和讨论、生成简短回复；角色成员只分类、不回复。已有类型标签保留，其他 Issue 可继续分析。发布前分别复查标签、状态、角色和讨论，追加标签并更新或创建本账号的一条回复，两项都回读验证。

手动补跑：选择 **Community 1**，填写 `issue_url`。`publish=false` 只生成分析和分类，不发评论也不挂标签。结果保留七天。

### 2. PR CI 通过后回复（自动，所有 PR）

手动指定 PR 编号。Action 要求 PR 仍开启且含 `ci-pipeline-passed` 标签；PR 作者角色不影响回复资格。

Action 查询当前状态、分页查重并发送检视提醒；同一 PR 串行执行。这里的查询用于发布前防止状态变化。手动补跑：选择 **Community 2**，填写 `pr_number`。

### 3. 简单 Issue 快速修复（仅手动，TRAE CN）

选择 **Community 3**，填写 `issue_number` 与 `validation_command`。这是独立的维护者手动任务，与分析与分类回复没有依赖或互相触发关系；无需先分析、不要求已有回复，也不限制 Issue 作者角色。

1. 固定 CATLASS master 源码和 Issue 讨论快照。
2. TRAE CN 只读分析根因，输出是否简单、修复说明与 unified patch。复杂或不明确的问题结束为 `needs-human`，不提 PR。
3. 独立步骤校验并应用补丁，最多十个文件，不接受自动化配置、symlink 或子模块修改；执行维护者指定验证命令。验证步骤不接收发布凭据。
4. 验证通过且讨论未变化，推送至发布账号已有的 CATLASS 个人 fork 的 `codex/issue-*` 分支，再向 `cann/catlass:master` 提 PR。
5. 回查 PR 后发布一条准确的 `compile` 评论，触发既有测试；重试时复用已创建的 PR 和评论。

运行环境是 GitHub Linux runner，无 NPU。验证命令需包含必要依赖准备，并应覆盖这个修复；例如 `python3 -m pytest tests/path/to/test_case.py`。需要设备才能确认的问题交由人工处理。发布账号的 AtomGit Token 需有 fork 推送、创建 PR 和评论权限。

### 4. PR 行级检视（仅手动，TRAE CN）

选择 **Community 4**，填写 `pr_number`。固定 PR head/base，读取 diff 和相关源码。模型只返回有代码依据的疑问，最多十条；发布程序要求每条对应当前 diff 的新增/修改行，不能把普通评论当作行级检视。PR 更新后拒绝发布，需重新运行；相同版本、相同问题重试不重复评论。无发现时正常结束，不发布评论，也不自动批准或合并。

使用 AtomGit [行级评论接口](https://docs.atomgit.com/docs/apis/post-api-v-5-repos-owner-repo-pulls-number-comments/)，发布后回查评论正文、作者、文件与 head。分析和发布证据保留七天。

## 依赖归档与 wheel 分发

DSL 构建池由 124（`dev-124-x64`）和 125（`dev-125-arm64`）组成，使用专用标签 `ascend-catlass-dsl-build`，配合 `self-hosted`、`Linux` 和实际架构 `X64`/`ARM64`。当前 NPUIR 准备和 wheel 构建使用同一构建池，nightly/release 沿用此设置。历史 NPUIR 20260720 和 AtomGit 发布仍使用 `publish`。每种架构保留一台符合标签的主机，扩容前需提供共享归档或显式绑定机器。构建机需要 Git、patch、Docker、Python >= 3.11，以及可写的依赖归档目录。

NPUIR 在每台构建机上保留日期归档。[npuir-local-archive](actions/npuir-local-archive.md) 先检查源码提交、架构与构建约定；命中时直接复用，缺失时由工作流编译。`latest` 只前移，wheel 构建仍选择匹配 CATLASS gitlink 的准确依赖。构建机使用最新版 Git 获取源码和子模块。

wheel 工作流在 x86_64 和 aarch64 主机上构建，无需主机安装或挂载 CANN。仅将遗留的 `ASCEND_HOME_PATH` 定义为空，以兼容上游 CMake 的变量存在性检查；依赖 CANN 的 bitcode 编译在运行时进行。nightly 发布开发版本到 GitHub 包索引；release 先检查 AtomGit 稳定 tag，再发布到 PyPI 和 AtomGit。AtomGit 分发使用 [atomgit-release](actions/atomgit-release.md)，已有相同附件可复用；`artifact_run_id` 可选择已有发布运行的验证产物，避免重新构建。

## 环境安装与镜像同步

CANN weekly 流程先锁定同一官方构建，再按唯一 `host-<IP中的点替换为连字符>` runner 标签逐台覆盖 11 台主机：原来的两台 X64 与新增的九台 ARM64，安装 Toolkit 与对应芯片的 ops。两台在线 X64 `bz` runner 在本机安装或通过 SSH 调度九台 ARM64，后者无需连接 GitHub。手动输入 `runner_label` 和 `target_arch` 可只安装一台；已管理主机的架构必须匹配。每个执行机使用自己的 `~/.ssh/cann_weekly_dispatch` 专用密钥及固定主机公钥的 `~/.ssh/cann_weekly_known_hosts`；专用 `~/.ssh/cann_weekly_ssh_config` 将隔离目标通过 `179.182.2.2` 和数据网地址中转，仍以管理 IP 的 `HostKeyAlias` 校验主机公钥；跳板密钥仅允许转发到列出的目标 SSH 端口。目标机授权密钥带 `restrict` 和 root 所有的 `/usr/local/libexec/cann-weekly/ssh-entry.py` 强制入口，只接受校验后的 `install-weekly BUILD VERSION ARCH`，调用同目录 root 所有的 `install.sh`，不向目标发送 GitHub token。这些基础设施文件须在首次调度前部署。单台失败不会取消其他主机，日志产物按主机区分。安装路径为 `/opt/cann_weekly/YYYYMMDD`；`/opt` 链接到 `/home/opt`，安装器强制检查真实目录位于独立挂载的 LVM `/home` 下的 `/home/opt/cann_weekly`，下载包和解压临时文件也放在这里，避免写满系统盘。已成功的日期安装会跳过，`latest` 指向完成目录。安装不会更新驱动或固件，日志保存 30 天。

镜像同步从 `cann/catlass` 的 AtomGit 仓库拉取 `master` 和 tags，然后强制更新 GitHub `ascend-catlass/catlass` 对应分支与标签，包括清理不再存在的 tag。因此应把目标仓库作为镜像使用。

## 使用时需要哪些凭据

| 凭据或配置 | 使用流程 |
| --- | --- |
| `ATOMGIT_TOKEN`，为空时回退 `GITCODE_TOKEN` | PR 元数据、评论和标签；Issue 读取与发布；AtomGit Release。按使用范围授予权限 |
| `TRAE_CN_PAT` | TRAE CLI 企业登录，包含 TestPR 失败分析 |
| `TRAE_CN_HOST` | 可选的企业服务地址变量 |
| `CATLASS_DEPLOY_KEY` | 写入 GitHub 镜像仓库 |
| PyPI Trusted Publisher | 稳定版本的 PyPI 发布，绑定 `pypi` 环境与 release 工作流 |

Token 通过 Secret 传给需要它的步骤；不要放进源码、提示词或调用示例中的普通文本。

## 公共 Action 依赖

通用步骤引用 `yuantao313/actions` 的固定提交 `02defff4ec04b38b33adfaec06bcb1406f5a2150`；RDV 状态发布使用修复版本 `02defff4ec04b38b33adfaec06bcb1406f5a2150`。CATLASS Python 策略需要传输 helpers 时，工作流将同一版本检出到 `shared_actions`。本地忽略该目录；公共实现及其单元测试由上游维护。

凭据优先读取 `ATOMGIT_TOKEN`，未设置或为空时回退到原有 `GITCODE_TOKEN`，已有配置无需改名。发布环境保留原有标识 `gitcode-release` 及其权限配置。工作流入口文件已统一为 `atomgit` 名称。历史 NPUIR 20260720 保留诊断行为，仅更新上游域名和平台称谓。

## AI 分析结果如何传递

Issue 回复、手动修复、PR 检视与 CI 失败分析统一使用 [catlass-ai](actions/catlass-ai.md) 选择模型、企业地址和只读沙箱，组合公共安装与执行组件。下游读取同一份执行结果中的正文和模型记录，不再单独指定署名模型。修复流程把答复和执行记录一起保存为提案，供验证和发布共用。CLI 版本取自安装步骤输出；Issue URL 的默认值仅在调度入口定义。目标编号、源码版本、补丁与验证命令的核对仍保留，用于阻止过期或不匹配的结果被发布。
## 指定机器准备构建依赖

`build-ascendnpu-ir-20261013.yml` 和 `install-cann-weekly.yml` 支持手动指定一台机器。
填写 `runner_label`（机器独有的自定义标签，例如 `host-179-223-2-2`），并用
`target_arch` 选择 `x86_64` 或 `aarch64`。目标仍须匹配 `self-hosted`、`Linux`
和对应的 `X64` / `ARM64` 标签。标签不是 runner 显示名称，必须唯一匹配目标机器。

```sh
gh workflow run install-cann-weekly.yml --repo ascend-catlass/actions --ref main \
  -f runner_label=host-179-223-2-2 -f target_arch=x86_64
gh workflow run build-ascendnpu-ir-20261013.yml --repo ascend-catlass/actions --ref main \
  -f runner_label=host-179-223-2-2 -f target_arch=x86_64 \
  -f branch=feature/regbase -f ref=693abf31f3d88d13d30d9578fcf6513b90c0ee33 \
  -f use_mirror=true -f build_jobs=64
```

第二台机器使用 `host-179-228-2-2`，分别 dispatch 即可。留空 `runner_label` 时仍运行
原有双架构矩阵，`target_arch` 此时不筛选任务；定时 CANN 和原有 NPUIR 复用调用保持
原来的调度池。20260720 历史诊断入口未改动。两条流水线均只在 `main` 执行。

NPUIR 的归档仍写入目标机 `/opt/AscendNPU-IR`，CANN 写入 `/opt/cann_weekly`。
runner 用户须能运行 Docker 并具有现有安装步骤所需的免密 sudo 权限。
