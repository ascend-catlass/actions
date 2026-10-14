# 自动化能力概览

[中文](../zh/index.md) · [English](../en/index.md)

本仓库把 PR 测试、构建环境、社区协作和版本分发中的重复步骤封装成可复用 Action。工作流负责何时启动、在哪台机器运行和怎样串联步骤；Action 负责完成一个具体任务。


## 找到你需要的 Action

| Action | 做什么 |
| --- | --- |
| [community-repo-roles](actions/community-repo-roles.md) | 查询社区维护者与 Committer |
| [create-ascend-container](actions/create-ascend-container.md) | 创建昇腾测试容器 |
| [gitcode-api](actions/gitcode-api.md) | 调用 GitCode API |
| [gitcode-ci-passed](actions/gitcode-ci-passed.md) | CI 通过后提醒代码检视 |
| [gitcode-issue](actions/gitcode-issue.md) | 准备、回复或分配 GitCode Issue |
| [gitcode-pr-metadata](actions/gitcode-pr-metadata.md) | 读取并校验 PR 版本信息 |
| [gitcode-release](actions/gitcode-release.md) | 发布 GitCode Release 安装包 |
| [npuir-local-archive](actions/npuir-local-archive.md) | 复用本机 AscendNPU-IR 构建归档 |
| [prepare-ci-tests](actions/prepare-ci-tests.md) | 准备测试依赖并选择 NPU |
| [rdv-status](actions/rdv-status.md) | 把 RDV 测试状态写回 PR |
| [run-ci-tests](actions/run-ci-tests.md) | 运行 CATLASS 测试阶段 |
| [trae-cn](actions/trae-cn.md) | 运行 TRAE CN 分析任务 |

## 这些步骤怎样组合

1. PR 测试：读取 PR 版本 → 写入测试开始状态 → 准备环境与选卡 → 运行测试 → 写回结果。
2. CI 通过提醒：dev webhook 触发 → 查询 PR 当前状态 → 检查已有评论 → 发送检视提醒。
3. Issue 协作：查询作者及社区角色 → 分配给角色成员，或准备上下文 → 模型分析 → 发布答复。
4. 版本构建：查询或构建 NPUIR 归档 → 构建双架构 wheel → 验证并分发。

具体触发方式、定时任务和执行机器见[工作流说明](workflows.md)。


## 阅读调用示例

每页的 YAML 是 steps 片段，需要放进已有 workflow 的 job。`${{ secrets.NAME }}` 表示从 GitHub Secret 读取凭据；`${{ steps.xxx.outputs.yyy }}` 表示引用前序步骤结果。示例中的编号、路径和步骤名称要与实际任务一致。

源码示例引用 @main，以便与当前仓库保持一致；固定发布版本的调用方可改用已经核验的完整提交 SHA。Action 对外接口在各自 action.yml 中定义。


## 当前范围

手册覆盖 12 个自定义 Action。CANN weekly 安装、仓库镜像同步和 wheel 的整套构建分发目前由工作流与脚本实现，它们也在工作流说明中介绍，不被另算为 Action。自动化不自动批准代码检视或合并 PR。
