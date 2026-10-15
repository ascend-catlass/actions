# 分析 CI 失败原因

[中文](../../zh/actions/analyze-ci-failure.md) · [English](../../en/actions/analyze-ci-failure.md)

## 做什么

输入本仓库的 GitHub run 编号与 attempt，输出一份失败原因、日志依据与下一步建议。它不依赖 CATLASS、PR 编号或 RDV 评论，可以用于其他 CI 工作流。

## 执行过程

官方 actions/github-script 负责认证、分页和下载日志；本地小脚本只负责截取、脱敏、准备提示词和组装评论内容。模型安装复用 setup-trae-cn，执行复用 trae-cn。最多读取四个失败 job 的证据，不执行被测代码，在单独初始化的临时 Git 目录里只读分析。

## 使用前准备

Linux x64 GitHub 托管 runner，Git、Node 与 Bash。job 权限设为 `contents: read`、`actions: read`，提供 TRAE CN 企业 PAT；不需要 AtomGit 或其他发布凭据。Action 自行准备目录，无需检出业务仓库源码。

## 调用示例

```yaml
- id: diagnosis
  uses: ascend-catlass/actions/.github/actions/analyze-ci-failure@main
  with:
    github-token: ${{ github.token }}
    trae-pat: ${{ secrets.TRAE_CN_PAT }}
    run-id: ${{ github.run_id }}
    run-attempt: ${{ github.run_attempt }}
```

调用方可把 `steps.diagnosis.outputs.analysis-file` 上传为 artifact，或交给自己的评论/报告 Action。TestPR 用 rdv-status 将其附加到失败评论，分析组件不负责发布。

## 输入

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `github-token` | 是 | — | 当前仓库 Actions 读取权限 Token。 |
| `trae-pat` | 是 | — | TRAE CN 企业 PAT。 |
| `run-id` | 是 | — | 当前仓库的工作流运行编号。 |
| `run-attempt` | 否 | `1` | 精确选择重跑轮次。 |
| `host` | 否 | `""` | 可选企业 API 地址。 |
| `model` | 否 | `DeepSeek-V4.1-Flash` | 模型名称，同时用于署名。 |

## 输出

| 字段 | 说明 |
| --- | --- |
| `analysis-file` | Markdown 结果文件路径；分析不可用时为提示文字。 |
| `status` | analyzed 或 unavailable。 |

## 失败处理

没有失败 job、日志不可用或模型失败时输出 unavailable 提示。调用方仍应对整个 Action 超时、初始化失败准备兜底；TestPR 独立 report job 已处理此情况。模型预算五分钟，调用方决定整个 job 的超时与结果保存时间。
