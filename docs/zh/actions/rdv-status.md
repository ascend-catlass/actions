# 把 RDV 测试状态写回 PR

[中文](../../zh/actions/rdv-status.md) · [English](../../en/actions/rdv-status.md)

`rdv-status`

## 做什么

把测试开始与最终结果写回 GitCode PR：维护 RDV-RUNNING、RDV-SUCC、RDV-FAIL 标签，并发布带工作流链接的评论。

## 什么时候用

PR 测试启动时调用 start；测试完成后由报告步骤调用 finish。

## 执行过程

1. 清除已有 RDV 状态标签，保留其他标签。
2. start 添加 RDV-RUNNING 并发布开始评论。
3. finish 在 success 时添加 RDV-SUCC，否则添加 RDV-FAIL，再发布结果评论。

## 使用前准备

- Linux runner，Bash、curl、jq；Token 需要读取和修改 PR 标签及发表评论。
- 目前 API 目标固定为 cann/catlass；需提供工作流结果地址。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/rdv-status@main
  with:
    phase: 'start'
    pr-number: '123'
    token: ${{ secrets.GITCODE_TOKEN }}
    result-url: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `phase` | 是 | — | start 开始或 finish 结束。 |
| `pr-number` | 是 | — | cann/catlass 项目内的 PR 编号。 |
| `token` | 是 | — | 可修改 PR 标签并写评论的 GitCode Token。 |
| `result` | 否 | — | finish 使用的测试结果；只有 success 被判定为成功。 |
| `result-url` | 是 | — | 评论中发布的 CI 结果链接。 |
| `comment-id` | 否 | — | 保留字段；当前 finish 脚本不使用，也不会编辑此评论。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `comment-id` | start 新建的 GitCode 评论 ID；finish 不写该输出。 |

## 说明与常见问题

- 当前脚本的 finish 会新增结果评论，不会修改 start 的评论；comment-id 输入保留在接口中，但脚本未使用。
- finish 的 result 只有 success 被当作成功；失败、取消、跳过或空值都归为 RDV-FAIL。start 输出新评论 ID。
- 它不负责 CI 通过后的代码检视提醒；该提醒由 gitcode-ci-passed 处理。

## 实现与调用方

- [.github/actions/rdv-status/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/rdv-status/action.yml)
- [.github/actions/rdv-status/rdv-status.sh](https://github.com/ascend-catlass/actions/blob/main/.github/actions/rdv-status/rdv-status.sh)
- [.github/workflows/test-gitcode-pr.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/test-gitcode-pr.yml)
