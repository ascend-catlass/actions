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

## 四条社区流水线

| 流程 | 触发 | 结果 |
| --- | --- | --- |
| Issue 简要分析 | 非 Committer/维护者的公开 Issue 新建/重开，或手动 | TRAE CN 简要分析与回复 |
| PR CI 通过回复 | 开启 PR 新增通过标签，或手动 | 向全部 PR 作者发送一次检视提醒 |
| 简单 Issue 修复 | 仅手动 | TRAE CN 补丁、验证、提 PR、评论 compile |
| PR 行级检视 | 仅手动 | TRAE CN 针对变更行提出有依据的问题 |

另保留 PR 测试、每日构建、环境安装、版本发布和旧 NPUIR 问题定位入口。操作方法见[工作流说明](workflows.md)，详细构建配置见[运维说明](../en/operations.md)。

## 阅读调用示例

每页的 YAML 是 steps 片段，需要放进已有 workflow 的 job。`${{ secrets.NAME }}` 表示从 GitHub Secret 读取凭据；`${{ steps.xxx.outputs.yyy }}` 表示引用前序步骤结果。示例中的编号、路径和步骤名称要与实际任务一致。

源码示例引用 @main，以便与当前仓库保持一致；固定发布版本的调用方可改用已经核验的完整提交 SHA。Action 对外接口在各自 action.yml 中定义。


## 当前范围

手册覆盖 12 个自定义 Action。CANN weekly 安装、仓库镜像同步和 wheel 的整套构建分发目前由工作流与脚本实现，它们也在工作流说明中介绍，不被另算为 Action。自动化不自动批准代码检视或合并 PR。
