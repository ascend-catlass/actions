# 准备、回复或分配 GitCode Issue

[中文](../../zh/actions/gitcode-issue.md) · [English](../../en/actions/gitcode-issue.md)

`gitcode-issue`

## 做什么

把 Issue 自动化分成三个可复用步骤：prepare 整理 Issue 和源码上下文，publish 发布或更新本账号的自动回复，assign 给符合角色条件的作者发送分配命令评论。它本身不调用模型。

## 什么时候用

组合 Issue 分析流程，或把上下文准备与评论发布拆成独立步骤。

## 执行过程

1. prepare：必要时下载源码，读取 Issue 与讨论，生成可信模板和待分析上下文。
2. 模型分析由独立的 trae-cn Action 完成。
3. publish：重查 Issue 与讨论是否变化，再发布或更新回复并回查；assign：校验角色和开启状态，复用相同分配评论。

## 使用前准备

- Linux runner，Python 3、Git，具有 Issue 读取和评论写入权限的 Token。
- prepare 需要可信 prompt-template 文件；publish 需要此前的结果目录和模型答复文件；角色分流需 community-repo-roles 结果。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- uses: actions/checkout@v4
  with:
    repository: ascend-catlass/actions
    ref: main
    persist-credentials: false
- id: action
  uses: ascend-catlass/actions/.github/actions/gitcode-issue@main
  with:
    operation: 'prepare'
    token: ${{ secrets.GITCODE_TOKEN }}
    issue-url: 'https://gitcode.com/cann/catlass/issues/739'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `operation` | 是 | — | prepare、publish 或 assign。 |
| `token` | 是 | — | 用于 Issue 读取及评论发布的 GitCode Token。 |
| `issue-url` | 是 | — | 目标 GitCode Issue 的 HTTPS 地址。 |
| `worktree` | 否 | `_issue-source` | 源码目录；prepare 在目录不存在时下载源码。 |
| `prompt-template` | 否 | `.github/prompts/gitcode-issue-reply.md` | prepare 使用的可信 UTF-8 模板路径。 |
| `result-directory` | 否 | `_issue-result` | 上下文与发布证据的保存目录；prepare 和 publish 使用同一目录。 |
| `response-file` | 否 | `""` | publish 读取的模型最终答复文件。 |
| `model` | 否 | `DeepSeek-V4.1-Flash` | 公开答复末尾署名使用的实际模型名称。 |
| `roles-file` | 否 | `""` | 可选的社区角色 JSON 文件；用于重查作者资格，assign 时需要。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `comment-url` | 发布或复用评论的地址，具体操作未发表评论时可能没有该输出。 |
| `result-directory` | 上下文和发布证据目录。 |

## 说明与常见问题

- roles-file 在接口中可选；现有 Issue 工作流会提供它，并在准备和发布时重新校验作者资格。assign 操作需要角色结果。
- publish 前若 Issue 或讨论变化，会拒绝过期答复。当前简要分析工作流对角色成员直接跳过，不调用 assign；assign 仍是供其他调用方选择的可复用操作。
- reply-gitcode-issue.yml 的 publish 默认为 true；设为 false 可分析但不发布回复。当前工作流由符合条件的新建/重开 Issue hook 或手动触发，与手动修复工作流独立。

## 实现与调用方

- [.github/actions/gitcode-issue/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/gitcode-issue/action.yml)
- [scripts/gitcode_issue_reply.py](https://github.com/ascend-catlass/actions/blob/main/scripts/gitcode_issue_reply.py)
- [scripts/issue_reply_eligibility.py](https://github.com/ascend-catlass/actions/blob/main/scripts/issue_reply_eligibility.py)
- [.github/workflows/reply-gitcode-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-gitcode-issue.yml)
