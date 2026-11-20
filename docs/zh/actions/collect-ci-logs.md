# 截取 CI 失败日志

[中文](../../zh/actions/collect-ci-logs.md) · [English](../../en/actions/collect-ci-logs.md)

`collect-ci-logs`

## 做什么

读取一次 GitHub 运行（attempt）中失败 job 的日志，定位失败位置，截取前后共 200 行，脱敏后输出为 Markdown 评论附件。不做 AI 分析。

## 什么时候用

流水线在首个失败处即停止，失败点附近的日志已足够定位问题，无需模型推断。由调用方决定如何发布该附件。

## 执行过程

1. 用官方 `actions/github-script` 列出该 attempt 的失败 job（最多 4 个），逐个下载日志。
2. 小脚本在日志中从后向前匹配失败标记（`##[error]`、`[detect_npu][ERROR]`、`FAILED`、`Traceback`、`fatal:`、非零退出码等），取最靠后的一个作为失败位置。
3. 以该位置为中心截取指定行数，去除 ANSI 颜色与时间戳，并脱敏 token、密码、`Authorization` 头和 URL 内嵌凭据。
4. 写入 `analysis.md`；日志缺失、为空或找不到失败标记时写入“日志片段暂不可用”，仍返回可用附件。

## 使用前准备

- GitHub 托管 runner；`github-token` 需要该仓库的 Actions 读取权限。
- 只读取日志，不检出也不执行 PR 代码。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的运行编号与 attempt 按目标任务替换。

```yaml
- id: excerpt
  uses: ascend-catlass/actions/.github/actions/collect-ci-logs@main
  with:
    github-token: ${{ github.token }}
    run-id: ${{ github.run_id }}
    run-attempt: ${{ github.run_attempt }}
```

```yaml
- name: Save the comment attachment
  if: ${{ always() && steps.excerpt.outputs.excerpt-file != '' }}
  uses: actions/upload-artifact@v4
  with:
    name: rdv-failure-logs-${{ github.run_attempt }}
    path: ${{ steps.excerpt.outputs.excerpt-file }}
    retention-days: 7
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `github-token` | 是 | — | 具备调用仓库 Actions 读取权限的 GitHub token。 |
| `run-id` | 是 | — | 要检查的 GitHub 工作流运行编号。 |
| `run-attempt` | 否 | `1` | 要检查的尝试序号。 |
| `context-lines` | 否 | `200` | 失败标记前后保留的日志行数，取值 1–2000。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `excerpt-file` | Markdown 日志片段路径；不可用时为带有说明的附件。 |
| `status` | `collected` 或 `unavailable`。 |

## 说明与常见问题

- 每个失败 job 只输出一段片段；多个失败 job 依次列出。找不到任何失败标记时该步骤报错，由后续渲染步骤回退为“暂不可用”。
- 附件上限 60000 字节，超出时截断并附提示；完整日志链接始终附在末尾。
- 不调用任何模型，不需要 TRAE CN 凭据。

## 实现与调用方

- [.github/actions/collect-ci-logs/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/collect-ci-logs/action.yml)
- [.github/actions/collect-ci-logs/excerpt.cjs](https://github.com/ascend-catlass/actions/blob/main/.github/actions/collect-ci-logs/excerpt.cjs)
- [.github/workflows/test-atomgit-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-atomgit-pr.yml)
