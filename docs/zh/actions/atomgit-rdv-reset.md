# 重置 RDV 标签

[中文](../../zh/actions/atomgit-rdv-reset.md) · [English](../../en/actions/atomgit-rdv-reset.md)

`atomgit-rdv-reset`

## 做什么

从 Pull Request 上移除 `RDV-SUCC`、`RDV-FAIL`、`RDV-RUNNING` 三个标签。

这些标签表示某一次 RDV 运行的结果。PR 改动之后该结果已不适用，清掉标签，
让 PR 重新进入待测试状态。

## 什么时候用

PR 有实际更新、且带有上述任一标签时，由网关派发。

## 执行过程

1. 读取 PR 当前状态与标签。
2. PR 已关闭或已合并则直接结束。
3. 逐个删除存在的 RDV 标签。
4. 重新读取 PR，确认标签确实已移除；仍在则报错。

## 使用前准备

- GitHub-hosted Linux runner；Action 配置 Python 3.12。
- 可写 PR 标签的 ATOMGIT_TOKEN（为空时回退到 GITCODE_TOKEN）。
- 仅针对 cann/catlass。

## 调用示例

```yaml
- uses: ascend-catlass/actions/.github/actions/atomgit-rdv-reset@main
  with:
    pr-number: '123'
    token: ${{ secrets.ATOMGIT_TOKEN || secrets.GITCODE_TOKEN }}
```

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `pr-number` | 是 | — | cann/catlass 项目内的 PR 编号。 |
| `token` | 是 | — | 可写 PR 标签的 AtomGit Token。 |

## 输出

| 字段 | 说明 |
| --- | --- |
| `result` | `removed:<标签>`、`no_rdv_label` 或 `pr_not_open`。 |

## 说明

只动这三个 RDV 标签，其他标签不受影响。删除后必定复查，避免把失败当成功。
