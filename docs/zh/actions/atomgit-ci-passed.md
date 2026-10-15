# CI 通过后提醒代码检视

[中文](../../zh/actions/atomgit-ci-passed.md) · [English](../../en/actions/atomgit-ci-passed.md)

`atomgit-ci-passed`

## 做什么

确认 CATLASS PR 当前仍然开启、带有 ci-pipeline-passed 标签后，提醒贡献者联系 Committer 检视。已有同样提醒时不重复发送。

## 什么时候用

CI 通过标签触发的自动提醒，或维护者手动补发提醒。

## 执行过程

1. 通过 AtomGit API 查询 PR 的最新状态和标签。
2. 分页检查 PR 评论，查找当前或此前版本的提醒。
3. 仅在条件满足且尚未提醒时发送评论，输出处理结果。

## 使用前准备

- GitHub-hosted Linux runner；Action 配置 Python 3.12。
- 可读取 PR 并写入评论的 ATOMGIT_TOKEN（为空时回退到原有 GITCODE_TOKEN）；当前只针对 cann/catlass。

## 调用示例

以下是工作流的 steps 片段，不是完整工作流。示例中的源码目录、前序 step 输出和发布包应已准备好；编号及版本按目标任务替换。

```yaml
- id: action
  uses: ascend-catlass/actions/.github/actions/atomgit-ci-passed@main
  with:
    pr-number: '123'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `pr-number` | 是 | — | cann/catlass 项目内的 PR 编号。 |
| `token` | 是 | — | 可读 PR 并写评论的 AtomGit Token。 |

“必填”按 action.yml 标记；某些可选字段在特定操作下仍必须提供，见执行过程与说明。

## 输出

| 字段 | 说明 |
| --- | --- |
| `result` | commented：已发送；already_reminded：已有提醒；pr_not_open：PR 未开启；label_not_present：当前无通过标签。 |

## 说明与常见问题

- 提醒要求代码贡献先提出描述问题的 Issue、在 PR 中关联，并在检视和合入前确认；同时包含代码检视、较大特性的 SIG 讨论，以及联系 Committer 评论 rdvcompile 触发 Ascend 950 流水线。
- reply-atomgit-ci-passed.yml 对同一 PR 串行执行；其他工作流复用时也需按 PR 串行，避免并发检查后都发表评论。

## 实现与调用方

- [.github/actions/atomgit-ci-passed/action.yml](https://github.com/ascend-catlass/actions/blob/main/.github/actions/atomgit-ci-passed/action.yml)
- [scripts/atomgit_ci_passed.py](https://github.com/ascend-catlass/actions/blob/main/scripts/atomgit_ci_passed.py)
- [.github/workflows/reply-atomgit-ci-passed.yml](https://github.com/ascend-catlass/actions/blob/main/.github/workflows/reply-atomgit-ci-passed.yml)
