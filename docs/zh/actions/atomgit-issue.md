# 准备和回复 CATLASS AtomGit Issue

[中文](../../zh/actions/atomgit-issue.md) · [English](../../en/actions/atomgit-issue.md)

`atomgit-issue`

## 做什么

组合公共 Issue 上下文与评论 Action，保留 CATLASS 作者角色、回复措辞和旧评论迁移策略。本 Action 不执行模型。

## 什么时候用

组合 Issue 分析流程，或把上下文准备与评论发布拆成独立步骤。

## 执行过程

1. prepare：必要时下载源码，读取 Issue 与讨论，生成可信模板和待分析上下文。
2. 模型分析由独立的 公共 traecn Action 完成。
3. publish：重查 Issue 与讨论是否变化，再发布或更新回复并回查。

## 使用前准备

- Linux runner，Python 3、Git，具有 Issue 读取和评论写入权限的 Token。
- prepare 需要可信 prompt-template 文件；publish 需要此前的上下文目录和 TRAE 执行结果目录；角色分流需 community-repo-roles 结果。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- uses: actions/checkout@v4
  with:
    repository: ascend-catlass/actions
    ref: main
    persist-credentials: false
- id: action
  uses: ascend-catlass/actions/.github/actions/atomgit-issue@main
  with:
    operation: 'prepare'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
    issue-url: 'https://atomgit.com/cann/catlass/issues/739'
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `operation` | 是 | — | prepare 或 publish。 |
| `token` | 是 | — | 用于 Issue 读取及评论发布的 AtomGit Token。 |
| `issue-url` | 否 | `""` | prepare 必须提供的 Issue 地址；publish 从上下文读取，无需重复传入。 |
| `worktree` | 否 | `_issue-source` | 源码目录；prepare 在目录不存在时下载源码。 |
| `prompt-template` | 否 | `.github/prompts/atomgit-issue-reply.md` | prepare 使用的可信 UTF-8 模板路径。 |
| `result-directory` | 否 | `_issue-result` | 上下文与发布证据的保存目录；prepare 和 publish 使用同一目录。 |
| `stage-result` | 否 | `""` | publish 必须提供的 TRAE result-directory，内含同一次执行的 response.md 和 result.json。 |
| `roles-file` | 否 | `""` | 可选的社区角色 JSON 文件；用于重查作者资格。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `comment-url` | 发布或复用评论的地址，具体操作未发表评论时可能没有该输出。 |
| `result-directory` | 上下文和发布证据目录。 |

## 说明与常见问题

- 发布只传分析结果目录，正文和署名来自同一次成功执行。模型只在执行步骤选择；记录中未指定模型时不猜测署名。
- 工作流在分析前检查作者；发布时通过 roles-file 再次检查当前作者与讨论。
- 旧的本账号回复在检查通过后迁移到公共评论标记，重试继续更新同一条评论。
- 工作流为手动调度。publish=false 只生成分析，不发表评论。

## 实现与调用方

- [.github/actions/atomgit-issue/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/atomgit-issue/action.yml)
- [scripts/issue_reply_policy.py](https://github.com/ascend-catlass/actions/blob/main/scripts/issue_reply_policy.py)
- [scripts/issue_reply_eligibility.py](https://github.com/ascend-catlass/actions/blob/main/scripts/issue_reply_eligibility.py)
- [.github/workflows/reply-atomgit-issue.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-issue.yml)

上下文收集与评论发布引用 `yuantao313/actions/atomgit-issue-context`、`atomgit-issue-comment`。本仓仅保留 CATLASS 角色和回复策略；旧回复在状态与角色检查通过后迁移标记，继续复用同一条评论。调用前需把固定版本的公共 helpers 检出到 `shared_actions`。
