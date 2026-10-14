# GitCode stages

仓库中的 GitCode API 操作通过以下 composite stages 调用：

| Stage | 用途 |
| --- | --- |
| `gitcode-api` | 通用 v5 REST 请求，token 只在请求头，JSON 文件输入/输出 |
| `gitcode-issue` | `prepare` 获取 Issue、分页评论与源码上下文；`publish` 幂等发布并回查回复 |
| `gitcode-pr-metadata` | 获取 open PR 的 base/head ref 与 head SHA，并验证格式 |
| `rdv-status` | 既有 PR CI 状态标签和结果评论 |
| `gitcode-release` | 发布及验证既有 wheel Release bundle |

Issue workflow 先调用 `gitcode-issue` 的 `prepare`，再调用模型 stage，最后
调用 `publish`。GitCode token 不传给模型。Issue 或讨论变化时拒绝发布过时
答复；仅更新同一身份的自动回复，别人伪造的标记不会被覆盖。旧标记兼容迁移。

公开回复采用自然讨论语气，最后一行固定为 `By DeepSeek V4.1 Flash`。
不展示工具名称、流水线记录、源码 SHA 附注；源码版本、报告基线、模型与
发布回查结果保存在 artifact 中。此 workflow 显式使用 `DeepSeek-V4.1-Flash`，
不在调用失败时切换其他模型。

`gitcode-api` 输入为 `token`、`method`、`path`、可选 `body-file` 与
`body-encoding`（form/json）。输出 `response-file` 指向 runner 临时 JSON
文件。`path` 仅允许固定 `https://api.gitcode.com/api/v5` 下的路径。
此通用 stage 不替调用方决定发布权限或幂等策略；业务 stage 负责这些约束。

2026-10-14 已在 GitHub Linux worker 通过 40 项测试，并对 CATLASS Issue
#739 使用显式 DeepSeek-V4.1-Flash 完成获取、分析、发布和回查，重跑更新同一评论。
GitCode 的成功 PATCH/DELETE 可能返回空 body；通用 stage 兼容空响应，业务
stage 通过 GET 校验实际结果，不因空响应重复创建评论。

示例：

```yaml
- id: context
  uses: ascend-catlass/actions/.github/actions/gitcode-issue@main
  with:
    operation: prepare
    token: ${{ secrets.GITCODE_TOKEN }}
    issue-url: https://gitcode.com/cann/catlass/issues/739
    prompt-template: .github/prompts/gitcode-issue-reply.md
- id: analyze
  uses: ascend-catlass/actions/.github/actions/trae-cn@main
  with:
    trae-pat: ${{ secrets.TRAE_CN_PAT }}
    model: DeepSeek-V4.1-Flash
    working-directory: _issue-source
    prompt-file: .trae-issue-context/prompt.md
- uses: ascend-catlass/actions/.github/actions/gitcode-issue@main
  with:
    operation: publish
    token: ${{ secrets.GITCODE_TOKEN }}
    issue-url: https://gitcode.com/cann/catlass/issues/739
    response-file: ${{ steps.analyze.outputs.response-file }}
    model: DeepSeek-V4.1-Flash
```

业务 stages 的脚本从 action 自身 checkout 读取，远程使用不依赖调用方拥有
`scripts/`。生产调用可以将 `@main` 固定为已验证的完整提交 SHA。
