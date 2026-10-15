# 自动化能力概览

[中文](../zh/index.md) · [English](../en/index.md)

本仓库维护 CATLASS 的测试、构建、社区策略与发布步骤，通用能力直接引用 [yuantao313/actions](https://github.com/yuantao313/actions)。工作流负责何时启动、在哪台机器运行和怎样串联步骤；Action 负责完成一个具体任务。


## 找到你需要的 Action

| Action | 做什么 |
| --- | --- |
| [analyze-ci-failure](actions/analyze-ci-failure.md) | 分析任意 GitHub CI 失败日志，返回可供评论使用的说明 |
| [community-repo-roles](actions/community-repo-roles.md) | 查询社区维护者与 Committer |
| [create-ascend-container](actions/create-ascend-container.md) | 创建昇腾测试容器 |
| [atomgit-api](https://github.com/yuantao313/actions/tree/fbfd9b229556d974d5aee35dafdf9dffe976facd/atomgit-api) | 调用 AtomGit API |
| [atomgit-ci-passed](actions/atomgit-ci-passed.md) | CI 通过后提醒代码检视 |
| [atomgit-issue](actions/atomgit-issue.md) | 准备、回复或分配 AtomGit Issue |
| [atomgit-pr-metadata](https://github.com/yuantao313/actions/tree/fbfd9b229556d974d5aee35dafdf9dffe976facd/atomgit-pr-metadata) | 读取并校验 PR 版本信息 |
| [atomgit-release](actions/atomgit-release.md) | 发布 AtomGit Release 安装包 |
| [npuir-local-archive](actions/npuir-local-archive.md) | 复用本机 AscendNPU-IR 构建归档 |
| [prepare-ci-tests](actions/prepare-ci-tests.md) | 准备测试依赖并选择 NPU |
| [rdv-status](actions/rdv-status.md) | 把 RDV 测试状态写回 PR |
| [run-ci-tests](actions/run-ci-tests.md) | 运行 CATLASS 测试阶段 |
| [setup-trae-cn](https://github.com/yuantao313/actions/tree/fbfd9b229556d974d5aee35dafdf9dffe976facd/setup-traecn) | 安装固定版本的官方 TRAE CN CLI |
| [trae-cn](https://github.com/yuantao313/actions/tree/fbfd9b229556d974d5aee35dafdf9dffe976facd/traecn) | 运行 TRAE CN 分析任务 |

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

手册覆盖 10 个 CATLASS 专用 Action；通用组件由 [yuantao313/actions](https://github.com/yuantao313/actions) 维护。CANN weekly 安装、仓库镜像同步和 wheel 的整套构建分发目前由工作流与脚本实现，它们也在工作流说明中介绍，不被另算为 Action。自动化不自动批准代码检视或合并 PR。
