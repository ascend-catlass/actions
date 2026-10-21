# Issue 自动分类

[English](../../en/actions/atomgit-issue-label.md) · [中文](../../zh/actions/atomgit-issue-label.md)

## 用途

Community 5 覆盖所有作者的新建公开 Issue，包括 Committer 和维护者。复用统一 AI 阶段，
模型不接收发布凭据。分页读取仓库标签，从实时存在的类型标签中选取候选：documentation、
feature、bug-report、wontfix、question、enhancement、bug、kind/feature、requirement、
tech-debt、invalid、duplicate、RFC。模型只选一个，不新建标签；信息不足不应直接判为 wontfix。

发布阶段同时读取成功模型阶段的响应和执行记录，复查 Issue 内容、状态、标签和候选列表，
只追加一个类型标签并回读验证。保留人工分类和其他标签。分析期间内容变化则拒绝发布，
已关闭或保密 Issue 跳过。独立分析流水线的新评论不会干扰分类。

## 示例

从本仓 checkout 调用，按工作流固定版本准备 shared_actions；模型步骤放在 prepare/publish 之间。

```yaml
- uses: ascend-catlass/actions/.github/actions/atomgit-issue-label@main
  with:
    operation: prepare
    issue-number: '739'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
```

## 输入

| 输入 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `operation` | 是 | — | prepare 或 publish |
| `token` | 是 | — | Issue/标签读取和挂标签权限 |
| `issue-number` | 否 | `""` | prepare 必填，cann/catlass Issue 编号 |
| `result-directory` | 否 | `_issue-label-result` | 上下文和发布证据目录 |
| `stage-result` | 否 | `""` | publish 必填，成功模型阶段结果 |

## 输出

| 输出 | 说明 |
| --- | --- |
| `analyze` | 准备完成且需要分类时为 true |
| `result` | ready、labeled、already_classified、issue_not_open 或 confidential_issue |

## 运维

新建/open 事件独立触发，不受现有简要分析流程的角色过滤影响；reopen/update 不重分类。
可手动补跑，publish=false 只分析。按 Issue 串行并在发布前查重，应对重复投递。
不新建标签、不评论、不关闭 Issue，也不自动触发修复。
